# Note that this file should be included directly in every Makefile inside each lab's folder.
# This sets up the environment variable for lab's Makefile.

ifndef LABROOT
LABROOT := $(CURDIR)/..
endif

SCRIPTS := $(LABROOT)/Scripts

ifeq (,$(LAB))
$(error LAB is not set!)
endif


LABDIR  := $(LABROOT)/Lab$(LAB)
SCRIPTS := $(LABROOT)/Scripts
GRADER  ?= $(SCRIPTS)/grader.sh

# Toolchain Configuration
ifeq ($(shell command -v gdb-multiarch 2> /dev/null),)
# Default to gdb if gdb-multiarch is not available
# This is only the case on debian-based distros
	GDB := gdb
else
	GDB := gdb-multiarch
endif

DOCKER ?= docker
DOCKER_IMAGE ?= ipads/oslab:25.03
DOCKER_CMD := $(SCRIPTS)/docker.sh
HAS_DOCKER := $(shell command -v $(DOCKER) 2>/dev/null)
CAN_USE_DOCKER := $(shell $(DOCKER_CMD) info >/dev/null 2>&1 && echo 1)
HAS_KVM := $(shell test -e /dev/kvm && echo 1 || echo 0)
DOCKER_TTY := $(shell test -t 1 && echo -t)
ifeq ($(CAN_USE_DOCKER),)
DOCKER_RUN ?=
else
ifneq ($(wildcard /.dockerenv)$(wildcard /run/.containerenv),)
DOCKER_RUN ?=
else
DOCKER_RUN ?= $(DOCKER_CMD) run -i $(DOCKER_TTY) --rm \
		-e SCRIPTS=$(SCRIPTS) \
		-e LABROOT=$(LABROOT) \
		-e LABDIR=$(LABDIR) \
		-e "TIMEOUT=$(TIMEOUT)" \
		-e LAB=$(LAB) \
		-u $(shell id -u $(USER)):$(shell id -g $(USER)) \
		-v $(LABROOT):$(LABROOT) -w $(CURDIR) \
		--security-opt=seccomp:unconfined \
		--platform=linux/amd64 \
		$(DOCKER_IMAGE)
endif
endif
QEMU-SYS ?= qemu-system-aarch64
QEMU-USER ?= qemu-aarch64

# Timeout for grading
ifeq ($(HAS_KVM),1)
	TIMEOUT ?= 10
else
	TIMEOUT ?= 600
endif

ifeq ($(shell test $(LAB) -eq 0; echo $$?),1)
	QEMU := $(QEMU-SYS)
	ifeq ($(shell test $(LAB) -gt 4; echo $$?),0)
		include $(LABROOT)/Scripts/extras/lab$(LAB).mk
	else
		include $(LABROOT)/Scripts/kernel.mk
	endif
	include $(LABROOT)/Scripts/submit.mk
else
	QEMU := $(QEMU-USER)
endif
