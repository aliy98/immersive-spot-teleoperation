/**
 * @file main.cpp
 * @brief Operator-side Oculus client: RTSP receive, stereo OpenGL present, input pipe.
 *
 * Responsibilities
 * ----------------
 * 1. Open a GStreamer / OpenCV VideoCapture on
 *    `rtsp://<cloud-ip>:8554/spot-stream`.
 * 2. Split each side-by-side frame into left/right `cv::Mat`s on a capture
 *    thread (`__capture_runner__`) guarded by `ThreadData`.
 * 3. Upload both images as GL textures (`BindCVMat2GLTexture`) and draw a
 *    full-screen quad per eye with the shaders in `OVR_ZED_VS` / `OVR_ZED_FS`
 *    through the Oculus PC SDK swap chain.
 * 4. Convert the HMD pose quaternion to RPY (`quaternionToRPY`) and, together
 *    with the Quest thumbstick axes, pack six floats into the named pipe
 *    `\\.\pipe\MyPipe` consumed by `scripts/oculus_client.py`.
 *
 * Command line (see README)::
 *
 *     "ZED Stereo Passthrough.exe" <cloud-server-public-ip> ZED
 */
#define NOMINMAX

#include <stdio.h>
#include <string.h>

#include <iostream>
#include <Windows.h>

#include <GL/glew.h>

#include <stddef.h>

 /*Depending on the SDL version you are using, you may have to include SDL2/SDL.h or directly SDL.h (2.0.7)*/
#include <SDL.h>
#include <SDL_syswm.h>

#include <Extras/OVR_Math.h>
#include <OVR_CAPI.h>
#include <OVR_CAPI_GL.h>

#include <cuda.h>
#include <cuda_runtime.h>
#include <cuda_gl_interop.h>

#include <sl/Camera.hpp>

#include "Shader.hpp"

#include <opencv2/opencv.hpp>

#include <cmath>


using namespace std;

GLchar* OVR_ZED_VS =
"#version 330 core\n \
			layout(location=0) in vec3 in_vertex;\n \
			layout(location=1) in vec2 in_texCoord;\n \
			uniform uint isLeft; \n \
			out vec2 b_coordTexture; \n \
			void main()\n \
			{\n \
				if (isLeft == 1U)\n \
				{\n \
					b_coordTexture = in_texCoord;\n \
					gl_Position = vec4(in_vertex.x, in_vertex.y, in_vertex.z,1);\n \
				}\n \
				else \n \
				{\n \
					b_coordTexture = vec2(1.0 - in_texCoord.x, in_texCoord.y);\n \
					gl_Position = vec4(-in_vertex.x, in_vertex.y, in_vertex.z,1);\n \
				}\n \
			}";

GLchar* OVR_ZED_FS =
"#version 330 core\n \
			uniform sampler2D u_textureZED; \n \
			in vec2 b_coordTexture;\n \
			out vec4 out_color; \n \
			void main()\n \
			{\n \
				out_color = vec4(texture(u_textureZED, b_coordTexture).bgr,1); \n \
			}";


void BindCVMat2GLTexture(cv::Mat& image, GLuint& imageTexture)
{
    if (image.empty()) {
        std::cout << "image empty" << std::endl;
    }
    else {
        //glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE);
        glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);
        glGenTextures(1, &imageTexture);
        glBindTexture(GL_TEXTURE_2D, imageTexture);

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);

        // Set texture clamping method
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP);

        cv::cvtColor(image, image, cv::COLOR_RGB2BGR);

        glTexImage2D(GL_TEXTURE_2D,         // Type of texture
            0,                   // Pyramid level (for mip-mapping) - 0 is the top level
            GL_RGB,              // Internal colour format to convert to
            image.cols,          // Image width  i.e. 640 for Kinect in standard mode
            image.rows,          // Image height i.e. 480 for Kinect in standard mode
            0,                   // Border width in pixels (can either be 1 or 0)
            GL_RGB,              // Input image format (i.e. GL_RGB, GL_RGBA, GL_BGR etc.)
            GL_UNSIGNED_BYTE,    // Image data type
            image.ptr());        // The actual image data itself
    }
}

// Packed data for threaded computation
struct ThreadData {
    std::mutex mtx;
    cv::Mat leftImage;
    cv::Mat rightImage;
    bool run;
    bool new_frame;
};

// Video capture thread
void __capture_runner__(ThreadData& thread_data, cv::VideoCapture cv_capture) {
    cv::Mat frame;
    // Loop while the main loop is not over
    while (thread_data.run) {
        // try to grab a new image
        if (cv_capture.read(frame)) {
            // copy both left and right images
            thread_data.mtx.lock();
            // Define the first ROI (left part of the frame)
            cv::Rect roi1(0, 0, frame.cols / 2, frame.rows);
            thread_data.leftImage = frame(roi1).clone(); // Use clone() to copy the data

            // Define the second ROI (right part of the frame)
            cv::Rect roi2(frame.cols / 2, 0, frame.cols / 2, frame.rows);
            thread_data.rightImage = frame(roi2).clone(); // Use clone() to copy the data

            thread_data.mtx.unlock();
            thread_data.new_frame = true;
        }
        else
            sl::sleep_ms(2);
    }
}

struct RPY {
    double roll, pitch, yaw;
};

RPY quaternionToRPY(ovrTrackingState ts) {
    RPY rpy;
    double w, x, y, z;

    w = ts.HeadPose.ThePose.Orientation.w;
    x = ts.HeadPose.ThePose.Orientation.x;
    y = ts.HeadPose.ThePose.Orientation.y;
    z = ts.HeadPose.ThePose.Orientation.z;

    // Pitch (x-axis rotation)
    double sinr_cosp = 2 * (w * x + y * z);
    double cosr_cosp = 1 - 2 * (x * x + y * y);
    rpy.pitch = std::atan2(sinr_cosp, cosr_cosp);

    // Yaw (y-axis rotation)
    double sinp = 2 * (w * y - z * x);
    if (std::abs(sinp) >= 1)
        rpy.yaw = std::copysign(M_PI / 2, sinp); // use 90 degrees if out of range
    else
        rpy.yaw = std::asin(sinp);

    // Roll (z-axis rotation)
    double siny_cosp = 2 * (w * z + x * y);
    double cosy_cosp = 1 - 2 * (y * y + z * z);
    rpy.roll = std::atan2(siny_cosp, cosy_cosp);

    return rpy;
}

int main(int argc, char** argv) {
    // Initialize SDL2's context
    SDL_Init(SDL_INIT_VIDEO);
    // Initialize Oculus' context
    ovrResult result = ovr_Initialize(nullptr);
    if (OVR_FAILURE(result)) {
        std::cout << "ERROR: Failed to initialize libOVR" << std::endl;
        SDL_Quit();
        return -1;
    }

    ovrSession session;
    ovrGraphicsLuid luid;
    // Connect to the Oculus headset
    result = ovr_Create(&session, &luid);
    if (OVR_FAILURE(result)) {
        std::cout << "ERROR: Oculus Rift not detected" << std::endl;
        ovr_Shutdown();
        SDL_Quit();
        return -1;
    }

    int x = SDL_WINDOWPOS_CENTERED, y = SDL_WINDOWPOS_CENTERED;
    int winWidth = 1280;
    int winHeight = 720;
    Uint32 flags = SDL_WINDOW_OPENGL | SDL_WINDOW_SHOWN;
    // Create SDL2 Window
    SDL_Window* window = SDL_CreateWindow("Stereo Passthrough", x, y, winWidth, winHeight, flags);
    // Create OpenGL context
    SDL_GLContext glContext = SDL_GL_CreateContext(window);
    // Initialize GLEW
    glewInit();
    // Turn off vsync to let the compositor do its magic
    SDL_GL_SetSwapInterval(0);

    // Create a struct which contains the sl::Camera and the associated data
    ThreadData thread_data;

    if (argc < 2) {
        std::cerr << "Error: No arguments provided." << std::endl;
        ovr_Shutdown();
        SDL_Quit();
        return -1;
    }

    std::string ip_address;
    std::string image_source;
    ip_address = argv[1];
    image_source = argv[2];
    /*if (argc < 3) 
        image_source = "ZED";
    else {
        if (argv[2] == "ZED" || argv[2] == "SPOT") 
            image_source = argv[2];
        else {
            std::cout << argv[2] << std::endl;
            std::cerr << "Error: Image source is not valid." << std::endl;
            ovr_Shutdown();
            SDL_Quit();
            return -1;
        }
    }*/

    std::string pipeline;

    if (image_source == "SPOT")
        pipeline = "rtspsrc location=rtsp://" + ip_address + ":8554/spot-stream latency=0 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! videoscale ! video/x-raw,width=1280,height=720,format=GRAY8 ! appsink";
    else 
        pipeline = "rtspsrc location=rtsp://" + ip_address + ":8554/spot-stream latency=0 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! videoscale ! video/x-raw,width=1280,height=240,format=GRAY8 ! appsink";

    cv::VideoCapture cv_capture(pipeline, cv::CAP_GSTREAMER);

    // Check if the video stream is opened successfully
    if (!cv_capture.isOpened()) {
        std::cout << "Failed to open video stream or file!" << std::endl;
        cv_capture.release();
        ovr_Destroy(session);
        ovr_Shutdown();
        return -1; // Exit if the stream or file is not opened
    }

    auto captureWidth = static_cast<int>(cv_capture.get(cv::CAP_PROP_FRAME_WIDTH));
    auto captureHeight = static_cast<int>(cv_capture.get(cv::CAP_PROP_FRAME_HEIGHT));

    //sl::uchar4 dark_bckgrd(44, 44, 44, 255);
    GLuint captureTextureID[2];
    glGenTextures(2, captureTextureID);
    for (int eye = 0; eye < 2; eye++) {
        // Generate OpenGL texture
        glBindTexture(GL_TEXTURE_2D, captureTextureID[eye]);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, captureWidth, captureHeight, 0, GL_BGRA, GL_UNSIGNED_BYTE, NULL);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    }

    // Register texture
    cudaGraphicsResource* cimg_l;
    cudaGraphicsResource* cimg_r;
    cudaError_t  err = cudaGraphicsGLRegisterImage(&cimg_l, captureTextureID[ovrEye_Left], GL_TEXTURE_2D, cudaGraphicsRegisterFlagsWriteDiscard);
    cudaError_t  err2 = cudaGraphicsGLRegisterImage(&cimg_r, captureTextureID[ovrEye_Right], GL_TEXTURE_2D, cudaGraphicsRegisterFlagsWriteDiscard);
    if (err != cudaSuccess || err2 != cudaSuccess)
        std::cout << "ERROR: cannot create CUDA texture : " << err << std::endl;

    float pixel_density = 1.75f;
    ovrHmdDesc hmdDesc = ovr_GetHmdDesc(session);
    ovrInputState InputState;
    // Get the texture sizes of Oculus eyes
    ovrSizei textureSize0 = ovr_GetFovTextureSize(session, ovrEye_Left, hmdDesc.DefaultEyeFov[0], pixel_density);
    ovrSizei textureSize1 = ovr_GetFovTextureSize(session, ovrEye_Right, hmdDesc.DefaultEyeFov[1], pixel_density);
    // Compute the final size of the render buffer
    ovrSizei bufferSize;
    bufferSize.w = textureSize0.w + textureSize1.w;
    bufferSize.h = std::max(textureSize0.h, textureSize1.h);

    // Initialize OpenGL swap textures to render
    ovrTextureSwapChain textureChain = nullptr;
    // Description of the swap chain
    ovrTextureSwapChainDesc descTextureSwap = {};
    descTextureSwap.Type = ovrTexture_2D;
    descTextureSwap.ArraySize = 1;
    descTextureSwap.Width = bufferSize.w;
    descTextureSwap.Height = bufferSize.h;
    descTextureSwap.MipLevels = 1;
    descTextureSwap.Format = OVR_FORMAT_R8G8B8A8_UNORM_SRGB;
    descTextureSwap.SampleCount = 1;
    descTextureSwap.StaticImage = ovrFalse;
    // Create the OpenGL texture swap chain
    result = ovr_CreateTextureSwapChainGL(session, &descTextureSwap, &textureChain);

    ovrErrorInfo errInf;
    if (OVR_SUCCESS(result)) {
        int length = 0;
        ovr_GetTextureSwapChainLength(session, textureChain, &length);
        for (int i = 0; i < length; ++i) {
            GLuint chainTexId;
            ovr_GetTextureSwapChainBufferGL(session, textureChain, i, &chainTexId);
            glBindTexture(GL_TEXTURE_2D, chainTexId);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        }
    }
    else {
        ovr_GetLastErrorInfo(&errInf);
        std::cout << "ERROR: failed creating swap texture " << errInf.ErrorString << std::endl;
        ovr_Destroy(session);
        ovr_Shutdown();
        SDL_GL_DeleteContext(glContext);
        SDL_DestroyWindow(window);
        SDL_Quit();
        return -1;
    }
    // Generate frame buffer to render
    GLuint fboID;
    glGenFramebuffers(1, &fboID);
    // Generate depth buffer of the frame buffer
    GLuint depthBuffID;
    glGenTextures(1, &depthBuffID);
    glBindTexture(GL_TEXTURE_2D, depthBuffID);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    GLenum internalFormat = GL_DEPTH_COMPONENT24;
    GLenum type = GL_UNSIGNED_INT;
    glTexImage2D(GL_TEXTURE_2D, 0, internalFormat, bufferSize.w, bufferSize.h, 0, GL_DEPTH_COMPONENT, type, NULL);

    // Create a mirror texture to display the render result in the SDL2 window
    ovrMirrorTextureDesc descMirrorTexture;
    memset(&descMirrorTexture, 0, sizeof(descMirrorTexture));
    descMirrorTexture.Width = winWidth;
    descMirrorTexture.Height = winHeight;
    descMirrorTexture.Format = OVR_FORMAT_R8G8B8A8_UNORM_SRGB;

    ovrMirrorTexture mirrorTexture = nullptr;
    result = ovr_CreateMirrorTextureGL(session, &descMirrorTexture, &mirrorTexture);
    if (!OVR_SUCCESS(result)) {
        ovr_GetLastErrorInfo(&errInf);
        std::cout << "ERROR: Failed to create mirror texture " << errInf.ErrorString << std::endl;
    }
    GLuint mirrorTextureId;
    ovr_GetMirrorTextureBufferGL(session, mirrorTexture, &mirrorTextureId);

    GLuint mirrorFBOID;
    glGenFramebuffers(1, &mirrorFBOID);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, mirrorFBOID);
    glFramebufferTexture2D(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, mirrorTextureId, 0);
    glFramebufferRenderbuffer(GL_READ_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, 0);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
    // Frame index used by the compositor, it needs to be updated each new frame
    long long frameIndex = 0;

    // FloorLevel will give tracking poses where the floor height is 0
    ovr_SetTrackingOriginType(session, ovrTrackingOrigin_FloorLevel);

    // Initialize a default Pose
    ovrPosef eyeRenderPose[2];
    ovrPosef hmdToEyeOffset[2];

    // Get the Oculus view scale description
    double sensorSampleTime;

    // Create and compile the shader's sources
    Shader shader(OVR_ZED_VS, OVR_ZED_FS);

    // Compute the useful part of the ZED image
    unsigned int widthFinal = bufferSize.w / 2;
    float heightGL = 1.f;
    float widthGL = 1.f;
    if (captureWidth > 0.f) {
        unsigned int heightFinal = captureHeight * widthFinal / (float)captureWidth;
        // Convert this size to OpenGL viewport's frame's coordinates
        heightGL = (heightFinal) / (float)(bufferSize.h);
        widthGL = ((captureWidth * (heightFinal / (float)captureHeight)) / (float)widthFinal);
    }
    else {
        std::cout << "WARNING: Video capture parameters got wrong values."
            "Default vertical and horizontal FOV are used."
            << std::endl;
    }

    // Compute the Horizontal Oculus' field of view with its parameters
    float ovrFovH = (atanf(hmdDesc.DefaultEyeFov[0].LeftTan) + atanf(hmdDesc.DefaultEyeFov[0].RightTan));
    // Compute the Vertical Oculus' field of view with its parameters
    float ovrFovV = (atanf(hmdDesc.DefaultEyeFov[0].UpTan) + atanf(hmdDesc.DefaultEyeFov[0].DownTan));

    // Compute the center of the optical lenses of the headset
    float offsetLensCenterX = ((atanf(hmdDesc.DefaultEyeFov[0].LeftTan)) / ovrFovH) * 2.f - 1.f;
    float offsetLensCenterY = ((atanf(hmdDesc.DefaultEyeFov[0].UpTan)) / ovrFovV) * 2.f - 1.f;

    // Create a rectangle with the computed coordinates and push it in GPU memory
    struct GLScreenCoordinates {
        float left, up, right, down;
    } screenCoord;


    if (image_source == "ZED") {
        screenCoord.up = heightGL + offsetLensCenterY;
        screenCoord.down = heightGL - offsetLensCenterY;
        screenCoord.right = widthGL * .75 + offsetLensCenterX;
        screenCoord.left = widthGL * .75 - offsetLensCenterX;
    } else if (image_source == "SPOT") {
        screenCoord.up = heightGL / 2 + offsetLensCenterY;
        screenCoord.down = heightGL / 2 - offsetLensCenterY;
        screenCoord.right = widthGL / 2 + offsetLensCenterX;
        screenCoord.left = widthGL / 2 - offsetLensCenterX;
    }
    

    float rectVertices[12] = { -screenCoord.left, -screenCoord.up, 0, screenCoord.right, -screenCoord.up, 0, screenCoord.right, screenCoord.down, 0, -screenCoord.left, screenCoord.down, 0 };
    GLuint rectVBO[3];
    glGenBuffers(1, &rectVBO[0]);
    glBindBuffer(GL_ARRAY_BUFFER, rectVBO[0]);
    glBufferData(GL_ARRAY_BUFFER, sizeof(rectVertices), rectVertices, GL_STATIC_DRAW);

    float rectTexCoord[8] = { 0, 1, 1, 1, 1, 0, 0, 0 };
    glGenBuffers(1, &rectVBO[1]);
    glBindBuffer(GL_ARRAY_BUFFER, rectVBO[1]);
    glBufferData(GL_ARRAY_BUFFER, sizeof(rectTexCoord), rectTexCoord, GL_STATIC_DRAW);

    unsigned int rectIndices[6] = { 0, 1, 2, 0, 2, 3 };
    glGenBuffers(1, &rectVBO[2]);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, rectVBO[2]);
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, sizeof(rectIndices), rectIndices, GL_STATIC_DRAW);

    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);
    glBindBuffer(GL_ARRAY_BUFFER, 0);

    // Initialize a boolean that will be used to stop the application�s loop and another one to pause/unpause rendering
    bool end = false;
    // SDL variable that will be used to store input events
    SDL_Event events;
    // This boolean is used to test if the application is focused
    bool isVisible = true;

    // Enable the shader
    glUseProgram(shader.getProgramId());
    // Bind the Vertex Buffer Objects of the rectangle that displays video capture images

    // vertices
    glEnableVertexAttribArray(Shader::ATTRIB_VERTICES_POS);
    glBindBuffer(GL_ARRAY_BUFFER, rectVBO[0]);
    glVertexAttribPointer(Shader::ATTRIB_VERTICES_POS, 3, GL_FLOAT, GL_FALSE, 0, 0);
    // indices
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, rectVBO[2]);
    // texture coordinates
    glEnableVertexAttribArray(Shader::ATTRIB_TEXTURE2D_POS);
    glBindBuffer(GL_ARRAY_BUFFER, rectVBO[1]);
    glVertexAttribPointer(Shader::ATTRIB_TEXTURE2D_POS, 2, GL_FLOAT, GL_FALSE, 0, 0);

    // Set thread variables
    thread_data.run = true;
    thread_data.new_frame = true;
    // Launch capture video thread
    //
    std::thread runner(__capture_runner__, std::ref(thread_data), cv_capture);

    cudaGraphicsMapResources(1, &cimg_l, 0);
    cudaGraphicsMapResources(1, &cimg_r, 0);

    // Execute python script
	printf("Executing python script...\n");
	char currentDir[MAX_PATH];
	GetCurrentDirectory(MAX_PATH, currentDir);
	printf(currentDir);
	const char* pythonScript = "\\..\\..\\scripts\\oculus_client.py ";
	std::string command = "start cmd /k python " + std::string(currentDir) + std::string(pythonScript) + ip_address;
	if (system(command.c_str()) != 0) {
		std::cerr << "Error executing Python script" << std::endl;
		return 1;
	}

	// Create named pipe
	LPCSTR pipeName = "\\\\.\\pipe\\MyPipe";
	HANDLE hPipe = CreateNamedPipe(
		pipeName,
		PIPE_ACCESS_OUTBOUND,
		PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
		1,
		0,
		0,
		0,
		NULL
	);

	if (hPipe == INVALID_HANDLE_VALUE) {
		std::cerr << "Error creating named pipe: " << GetLastError() << std::endl;
		return 1;
	}

	// Connect to the named pipe
	if (ConnectNamedPipe(hPipe, NULL) == FALSE) {
		std::cerr << "Error connecting to named pipe: " << GetLastError() << std::endl;
		CloseHandle(hPipe);
		return 1;
	}

    RPY orientation;
    
    // Main loop
    while (!end) {
        // While there is an event catched and not tested
        while (SDL_PollEvent(&events)) {
            // If a key is released
            if (events.type == SDL_KEYUP) {
                // If Q -> quit the application
                if (events.key.keysym.scancode == SDL_SCANCODE_Q)
                    end = true;
            }
        }

        // Get texture swap index where we must draw our frame
        GLuint curTexId;
        int curIndex;
        ovr_GetTextureSwapChainCurrentIndex(session, textureChain, &curIndex);
        ovr_GetTextureSwapChainBufferGL(session, textureChain, curIndex, &curTexId);

        // Call ovr_GetRenderDesc each frame to get the ovrEyeRenderDesc, as the returned values (e.g. HmdToEyeOffset) may change at runtime.
        hmdToEyeOffset[ovrEye_Left] = ovr_GetRenderDesc(session, ovrEye_Left, hmdDesc.DefaultEyeFov[ovrEye_Left]).HmdToEyePose;
        hmdToEyeOffset[ovrEye_Right] = ovr_GetRenderDesc(session, ovrEye_Right, hmdDesc.DefaultEyeFov[ovrEye_Right]).HmdToEyePose;

        // Get eye poses, feeding in correct IPD offset
        ovr_GetEyePoses2(session, frameIndex, ovrTrue, hmdToEyeOffset, eyeRenderPose, &sensorSampleTime);

        // If the application is focused
        if (isVisible) {
            // If successful grab a new capture image
            if (thread_data.new_frame) {
                // Update the capture frame counter
                thread_data.mtx.lock();
                cudaArray_t arrIm;
                cudaGraphicsSubResourceGetMappedArray(&arrIm, cimg_l, 0, 0);
                cudaMemcpy2DToArray(arrIm, 0, 0, thread_data.leftImage.data, thread_data.leftImage.step, thread_data.leftImage.cols * 4, thread_data.leftImage.rows, cudaMemcpyDeviceToDevice);

                cudaGraphicsSubResourceGetMappedArray(&arrIm, cimg_r, 0, 0);
                cudaMemcpy2DToArray(arrIm, 0, 0, thread_data.rightImage.data, thread_data.rightImage.step, thread_data.leftImage.cols * 4, thread_data.leftImage.rows, cudaMemcpyDeviceToDevice);
                thread_data.mtx.unlock();
                thread_data.new_frame = false;

                BindCVMat2GLTexture(thread_data.leftImage, captureTextureID[0]);
                BindCVMat2GLTexture(thread_data.rightImage, captureTextureID[1]);

                // Bind the frame buffer
                glBindFramebuffer(GL_FRAMEBUFFER, fboID);
                // Set its color layer 0 as the current swap texture
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, curTexId, 0);
                // Set its depth layer as our depth buffer
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, depthBuffID, 0);
                // Clear the frame buffer
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
                glClearColor(0, 0, 0, 1);

                // Render for each Oculus eye the equivalent video capture image
                for (int eye = 0; eye < 2; eye++) {
                    // Set the left or right vertical half of the buffer as the viewport
                    glViewport(eye == ovrEye_Left ? 0 : bufferSize.w / 2, 0, bufferSize.w / 2, bufferSize.h);
                    // Bind the left or right video capture image
                    glBindTexture(GL_TEXTURE_2D, eye == ovrEye_Left ? captureTextureID[ovrEye_Left] : captureTextureID[ovrEye_Right]);
                    // Bind the isLeft value
                    glUniform1ui(glGetUniformLocation(shader.getProgramId(), "isLeft"), eye == ovrEye_Left ? 1U : 0U);
                    // Draw the video capture image
                    glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, 0);
                }
                // Avoids an error when calling SetAndClearRenderSurface during next iteration.
                // Without this, during the next while loop iteration SetAndClearRenderSurface
                // would bind a framebuffer with an invalid COLOR_ATTACHMENT0 because the texture ID
                // associated with COLOR_ATTACHMENT0 had been unlocked by calling wglDXUnlockObjectsNV.
                glBindFramebuffer(GL_FRAMEBUFFER, fboID);
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, 0, 0);
                glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, 0, 0);
                // Commit changes to the textures so they get picked up frame
                ovr_CommitTextureSwapChain(session, textureChain);
            }
            // Do not forget to increment the frameIndex!
            frameIndex++;
        }

        /*
        Note: Even if we don't ask to refresh the framebuffer or if the Camera::grab()
              doesn't catch a new frame, we have to submit an image to the Rift; it
                  needs 75Hz refresh. Else there will be jumbs, black frames and/or glitches
                  in the headset.
         */
        ovrLayerEyeFov ld;
        ld.Header.Type = ovrLayerType_EyeFov;
        // Tell to the Oculus compositor that our texture origin is at the bottom left
        ld.Header.Flags = ovrLayerFlag_TextureOriginAtBottomLeft; // Because OpenGL | Disable head tracking
        // Set the Oculus layer eye field of view for each view
        for (int eye = 0; eye < 2; ++eye) {
            // Set the color texture as the current swap texture
            ld.ColorTexture[eye] = textureChain;
            // Set the viewport as the right or left vertical half part of the color texture
            if (image_source == "ZED")
                ld.Viewport[eye] = OVR::Recti(eye == ovrEye_Left ? 0 : (bufferSize.w / 2) + 200, 0, (bufferSize.w / 2) - 200, bufferSize.h);
            else if (image_source == "SPOT")
                ld.Viewport[eye] = OVR::Recti(eye == ovrEye_Left ? 0 : (bufferSize.w / 2) - 400, 0, (bufferSize.w / 2) + 400, bufferSize.h);
            // Set the field of view
            ld.Fov[eye] = hmdDesc.DefaultEyeFov[eye];
            // Set the pose matrix
            ld.RenderPose[eye] = eyeRenderPose[eye];
        }

        ld.SensorSampleTime = sensorSampleTime;

        ovrLayerHeader* layers = &ld.Header;
        // Submit the frame to the Oculus compositor
        // which will display the frame in the Oculus headset
        result = ovr_SubmitFrame(session, frameIndex, nullptr, &layers, 1);

        if (!OVR_SUCCESS(result)) {
            ovr_GetLastErrorInfo(&errInf);
            std::cout << "ERROR: failed to submit frame " << errInf.ErrorString << std::endl;
            end = true;
        }

        if (result == ovrSuccess && !isVisible) {
            std::cout << "The application is now shown in the headset." << std::endl;
        }
        isVisible = (result == ovrSuccess);

        // This is not really needed for this application but it may be useful for an more advanced application
        ovrSessionStatus sessionStatus;
        ovr_GetSessionStatus(session, &sessionStatus);
        if (sessionStatus.ShouldRecenter) {
            std::cout << "Recenter Tracking asked by Session" << std::endl;
            ovr_RecenterTrackingOrigin(session);
        }

        // Copy the frame to the mirror buffer
        // which will be drawn in the SDL2 image
        glBindFramebuffer(GL_READ_FRAMEBUFFER, mirrorFBOID);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
        GLint w = winWidth;
        GLint h = winHeight;
        glBlitFramebuffer(0, h, w, 0,
            0, 0, w, h,
            GL_COLOR_BUFFER_BIT, GL_NEAREST);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
        // Swap the SDL2 window
        SDL_GL_SwapWindow(window);

        // Query the HMD for ts current tracking state.
		ovrTrackingState ts = ovr_GetTrackingState(session, ovr_GetTimeInSeconds(), ovrTrue);
		ovr_GetInputState(session, ovrControllerType_Touch, &InputState);
		ovrVector2f rightStick = InputState.Thumbstick[ovrHand_Right];
		ovrVector2f leftStick = InputState.Thumbstick[ovrHand_Left];
		const float radialDeadZone = 0.5;
		if (std::abs(rightStick.x) < radialDeadZone) rightStick.x = 0.0;
		if (std::abs(rightStick.y) < radialDeadZone) rightStick.y = 0.0;

        orientation = quaternionToRPY(ts);

        printf(
		//	" Touch Lin Vel (XY): %4.2f  %4.2f\n"
		//	" Touch Rot Vel (Z):  %4.2f\n",
			" HMD Ang (YPR): %4.2f  %4.2f  %4.2f\n",
		//	rightStick.y, rightStick.x,
		//	leftStick.x,
			orientation.yaw, -orientation.pitch, -orientation.roll);
        //    ts.HeadPose.AngularVelocity.y, -ts.HeadPose.AngularVelocity.x, -ts.HeadPose.AngularVelocity.z);

		// Send float data
		//float data[] = {orientation.yaw, -orientation.pitch, -orientation.roll, rightStick.y, rightStick.x, leftStick.x};
        float data[] = {orientation.yaw, -orientation.pitch,  -orientation.roll, rightStick.y, rightStick.x, leftStick.x};
		
        DWORD bytesWritten;
		if (WriteFile(hPipe, data, sizeof(data), &bytesWritten, NULL) == FALSE) {
			std::wcerr << "Error writing to named pipe: " << GetLastError() << std::endl;
		}

    }

    // Close the pipe
	CloseHandle(hPipe);

    // Close the cv video capture context
    cv_capture.release();
    cv::destroyAllWindows();
    
    cudaGraphicsUnmapResources(1, &cimg_l);
    cudaGraphicsUnmapResources(1, &cimg_r);

    // Disable all OpenGL buffer
    glDisableVertexAttribArray(Shader::ATTRIB_TEXTURE2D_POS);
    glDisableVertexAttribArray(Shader::ATTRIB_VERTICES_POS);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
    glBindTexture(GL_TEXTURE_2D, 0);
    glUseProgram(0);
    glBindVertexArray(0);
    // Delete the Vertex Buffer Objects of the rectangle
    glDeleteBuffers(3, rectVBO);
    // Delete SDL, OpenGL and Oculus context
    ovr_DestroyTextureSwapChain(session, textureChain);
    ovr_DestroyMirrorTexture(session, mirrorTexture);
    ovr_Destroy(session);
    ovr_Shutdown();
    SDL_GL_DeleteContext(glContext);
    SDL_DestroyWindow(window);
    SDL_Quit();

    // Quit
    return 0;
}