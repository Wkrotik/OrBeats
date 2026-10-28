// Typed PS4 ABI declarations for the subset used here. OpenOrbis 0.5.4 has
// void() placeholders for several setters and sceSslTerm; do not include those.
// Signatures cross-checked with SDK Http/Net headers and independent references
// recorded in README. No emulator implementation code is copied.
#pragma once
#include <stddef.h>
#include <stdint.h>
extern "C" {
int32_t sceSysmoduleIsLoadedInternal(uint32_t id);
int32_t sceSysmoduleLoadModuleInternal(uint32_t id);
int32_t sceNetPoolCreate(const char* name, int32_t bytes, int32_t flags);
void sceNetPoolDestroy(int32_t id);
int32_t sceSslInit(size_t bytes);
int32_t sceSslTerm(int32_t id);
int32_t sceHttpInit(int32_t pool, int32_t ssl, size_t bytes);
int32_t sceHttpTerm(int32_t id);
int32_t sceHttpCreateTemplate(int32_t http, const char* user_agent, int32_t version, int32_t proxy);
int32_t sceHttpDeleteTemplate(int32_t id);
int32_t sceHttpSetAutoRedirect(int32_t id, int32_t enabled);
int32_t sceHttpSetAuthEnabled(int32_t id, int32_t enabled);
int32_t sceHttpSetCookieEnabled(int32_t id, int32_t enabled);
int32_t sceHttpSetInflateGZIPEnabled(int32_t id, int32_t enabled);
int32_t sceHttpSetResolveRetry(int32_t id, int32_t retries);
int32_t sceHttpSetResolveTimeOut(int32_t id, uint32_t microseconds);
int32_t sceHttpSetConnectTimeOut(int32_t id, uint32_t microseconds);
int32_t sceHttpSetSendTimeOut(int32_t id, uint32_t microseconds);
int32_t sceHttpSetRecvTimeOut(int32_t id, uint32_t microseconds);
int32_t sceHttpsEnableOption(int32_t id, uint32_t flags);
int32_t sceHttpCreateConnection(int32_t templ, const char* server, const char* scheme, uint16_t port, int32_t keep_alive);
int32_t sceHttpDeleteConnection(int32_t id);
int32_t sceHttpCreateRequestWithURL(int32_t connection, int32_t method, const char* url, uint64_t content_length);
int32_t sceHttpDeleteRequest(int32_t id);
int32_t sceHttpAddRequestHeader(int32_t id, const char* name, const char* value, int32_t mode);
int32_t sceHttpSendRequest(int32_t id, const void* body, size_t bytes);
int32_t sceHttpGetStatusCode(int32_t id, int32_t* status);
int32_t sceHttpGetLastErrno(int32_t id, int32_t* error);
int32_t sceHttpsGetSslError(int32_t id, int32_t* error, uint32_t* details);
int32_t sceHttpReadData(int32_t id, void* bytes, uint32_t capacity);
uint64_t sceKernelGetProcessTime(void);
}
