/* Project-local build root only, GPL-3.0-or-later.
 * A single-ID bubblewrap namespace cannot assign files to unmapped service IDs:
 * the kernel returns EINVAL, which old package postinst scripts treat as fatal.
 * Suppress only that ownership bookkeeping error in this isolated build root.
 * Never package/preload this library into OrBeats or use it on the host root.
 * Other ownership/permission/path errors retain their real result and errno.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <sys/types.h>
#include <unistd.h>

static int unmapped(int result, uid_t uid, gid_t gid) {
    if (result == -1 && errno == EINVAL && getuid() == 0 &&
        ((uid != 0 && uid != (uid_t)-1) || (gid != 0 && gid != (gid_t)-1)))
        return 0;
    return result;
}
int chown(const char *path, uid_t uid, gid_t gid) {
    int (*real)(const char *,uid_t,gid_t)=dlsym(RTLD_NEXT,"chown");
    return unmapped(real(path,uid,gid),uid,gid);
}
int lchown(const char *path, uid_t uid, gid_t gid) {
    int (*real)(const char *,uid_t,gid_t)=dlsym(RTLD_NEXT,"lchown");
    return unmapped(real(path,uid,gid),uid,gid);
}
int fchown(int fd, uid_t uid, gid_t gid) {
    int (*real)(int,uid_t,gid_t)=dlsym(RTLD_NEXT,"fchown");
    return unmapped(real(fd,uid,gid),uid,gid);
}
int fchownat(int dir, const char *path, uid_t uid, gid_t gid, int flags) {
    int (*real)(int,const char *,uid_t,gid_t,int)=dlsym(RTLD_NEXT,"fchownat");
    return unmapped(real(dir,path,uid,gid,flags),uid,gid);
}
