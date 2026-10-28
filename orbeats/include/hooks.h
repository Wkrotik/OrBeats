#ifndef HOOKS_H
#define HOOKS_H

#include <stdint.h>

void* find_symbol(const char* symbol_name);
void install_hook(void* original, void* replacement);

#endif
