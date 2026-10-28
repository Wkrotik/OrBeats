#ifndef BEAT_SABER_DELUXE_H
#define BEAT_SABER_DELUXE_H

#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include "hooks.h"

// Redirection Map
typedef struct {
    const char* original_path;
    const char* redirect_path;
} PathRedirect;

// Global redirection table
extern PathRedirect g_redirects[];
extern int g_redirect_count;

// Hook function for open
int (*orig_open)(const char* pathname, int flags, mode_t mode);
int hooked_open(const char* pathname, int flags, mode_t mode);

#endif
