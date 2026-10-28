# Separate GoldHEN plugin. Never installs or changes OrBeats' build outputs.
DEBUG ?= 0
TOOLCHAIN := $(OO_PS4_TOOLCHAIN)
INTDIR := obj$(if $(filter 1,$(DEBUG)),-debug,)
TARGET := orbeats_extras$(if $(filter 1,$(DEBUG)),_debug,).prx
CXXFLAGS := --target=x86_64-pc-freebsd12-elf -fPIC -funwind-tables -c -isysroot $(TOOLCHAIN) -isystem $(TOOLCHAIN)/include -isystem $(TOOLCHAIN)/include/c++/v1 -Iinclude -DORBEATS_PS4 -Wall -Wextra -Werror
ifeq ($(DEBUG),1)
CXXFLAGS += -g -O0
else
CXXFLAGS += -O2
endif
.PHONY: all clean
all: $(TARGET)
$(INTDIR):
	mkdir -p $@
OBJECTS := $(INTDIR)/main.o $(INTDIR)/scoresaber.o $(INTDIR)/transport.o $(INTDIR)/worker.o $(INTDIR)/leaderboard.o $(INTDIR)/cJSON.o
$(INTDIR)/main.o: src/main.cpp include/health.h include/health_activation.h include/leaderboard.h | $(INTDIR)
	clang++ $(CXXFLAGS) -o $@ $<
$(INTDIR)/scoresaber.o: src/scoresaber.cpp include/scoresaber.h third_party/cjson/cJSON.h | $(INTDIR)
	clang++ $(CXXFLAGS) -o $@ $<
$(INTDIR)/transport.o: src/transport.cpp include/transport.h include/scoresaber.h include/ps4_http.h | $(INTDIR)
	clang++ $(CXXFLAGS) -o $@ $<
$(INTDIR)/worker.o: src/worker.cpp include/worker.h include/transport.h | $(INTDIR)
	clang++ $(CXXFLAGS) -o $@ $<
$(INTDIR)/leaderboard.o: src/leaderboard.cpp $(wildcard include/*.h) $(wildcard ../orbeats/include/*.h) | $(INTDIR)
	clang++ $(CXXFLAGS) -o $@ $<
$(INTDIR)/cJSON.o: third_party/cjson/cJSON.c third_party/cjson/cJSON.h | $(INTDIR)
	clang $(CXXFLAGS) -DCJSON_NESTING_LIMIT=16 -fvisibility=hidden -o $@ $<
$(TARGET): $(OBJECTS) ../orbeats/link.x
	ld.lld -m elf_x86_64 -pie -e _init --script ../orbeats/link.x --eh-frame-hdr -L$(TOOLCHAIN)/lib $(TOOLCHAIN)/lib/crtprx.o $(OBJECTS) -lGoldHEN_Hook -lSceLibcInternal -lkernel -lSceNet -lSceSsl -lSceHttp -lSceSysmodule -o $(INTDIR)/orbeats_extras.elf
	$(TOOLCHAIN)/bin/linux/create-fself -in=$(INTDIR)/orbeats_extras.elf -out=$(INTDIR)/orbeats_extras.oelf --lib=$(TARGET) --paid 0x3800000000000011
clean:
	rm -f $(TARGET) $(OBJECTS) $(INTDIR)/orbeats_extras.elf $(INTDIR)/orbeats_extras.oelf
