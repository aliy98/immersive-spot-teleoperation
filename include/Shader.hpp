/**
 * @file Shader.hpp
 * @brief Minimal GLSL program wrapper used by the Oculus passthrough renderer.
 *
 * Compiles a vertex + fragment pair, binds the attribute locations used by
 * the stereo quad (`in_vertex` = 0, `in_texCoord` = 1) and exposes the
 * linked program id to `main.cpp`.
 */
#pragma once
#include <GL/glew.h>

class Shader {
public:
    Shader(GLchar* vs, GLchar* fs);
    ~Shader();

    GLuint getProgramId();

    static const GLint ATTRIB_VERTICES_POS = 0;
    static const GLint ATTRIB_TEXTURE2D_POS = 1;
private:
    bool compile(GLuint &shaderId, GLenum type, GLchar* src);
    GLuint verterxId_;
    GLuint fragmentId_;
    GLuint programId_;
};
