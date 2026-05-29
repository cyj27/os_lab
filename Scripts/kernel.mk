V ?= 0
Q := @
GRADER_V :=
ifeq ($(V), 1)
	Q :=
endif

ifeq ($(V), 2)
	Q :=
	GRADER_V := -v
endif

BUILDDIR := $(LABDIR)/build
KERNEL_IMG := $(BUILDDIR)/kernel.img
_QEMU := $(SCRIPTS)/qemu_wrapper.sh $(QEMU)
QEMU_GDB_PORT := 1234
ifeq ($(HAS_KVM),1)
QEMU_ACCEL :=
else
QEMU_ACCEL := -accel tcg,thread=multi
endif
QEMU_OPTS := $(QEMU_ACCEL) -machine raspi3b -nographic -serial mon:stdio -m size=1G -kernel $(KERNEL_IMG)
ifeq ($(CAN_USE_DOCKER),)
	CHBUILD := $(SCRIPTS)/chbuild --local
else
	CHBUILD := $(SCRIPTS)/chbuild
endif
SERIAL := $(shell python3 -c "import secrets, string; a = string.ascii_letters + string.digits; print(''.join(secrets.choice(a) for _ in range(13)))")

export LABROOT LABDIR SCRIPTS LAB TIMEOUT

all: build

defconfig:
	$(Q)$(CHBUILD) defconfig

build:
	$(Q)test -f $(LABDIR)/.config || $(CHBUILD) defconfig
	$(Q)$(CHBUILD) build
	$(Q)find -L $(LABDIR) -path */compile_commands.json \
       ! -path $(LABDIR)/compile_commands.json -print \
	   | python3 $(SCRIPTS)/merge_compile_commands.py

clean:
	$(Q)$(CHBUILD) clean
	$(Q)find -L $(LABDIR) -path */compile_commands.json -exec rm {} \;

distclean:
	$(Q)$(CHBUILD) distclean

qemu: build
	$(Q)$(_QEMU) $(QEMU_OPTS)

qemu-grade:
	$(SCRIPTS)/change_serial $(KERNEL_IMG) $(SERIAL)
	$(Q)$(_QEMU) $(QEMU_OPTS)

qemu-gdb: build
	$(Q)echo "[QEMU] Waiting for GDB Connection"
	$(Q)$(_QEMU) -S -gdb tcp::$(QEMU_GDB_PORT) $(QEMU_OPTS)

gdb:
	$(Q)$(GDB) --nx -x $(SCRIPTS)/gdb/gdbinit

official-grade-local:
	$(Q)$(MAKE) distclean >/dev/null 2>&1
	$(Q)(test -f $(LABDIR)/.config && cp $(LABDIR)/.config $(LABDIR)/.config.bak) || :
	$(Q)$(MAKE) build
	$(Q)$(GRADER) -t $(TIMEOUT) -f $(LABDIR)/scores.json $(GRADER_V) -s $(SERIAL) make SERIAL=$(SERIAL) qemu-grade
	$(Q)(test -f $(LABDIR)/.config.bak && cp $(LABDIR)/.config.bak $(LABDIR)/.config && rm $(LABDIR)/.config.bak) || :

grade:
	$(Q)if test -n "$(CAN_USE_DOCKER)"; then \
		$(MAKE) distclean >/dev/null 2>&1; \
		(test -f $(LABDIR)/.config && cp $(LABDIR)/.config $(LABDIR)/.config.bak) || :; \
		$(MAKE) build; \
		$(DOCKER_RUN) $(GRADER) -t $(TIMEOUT) -f $(LABDIR)/scores.json $(GRADER_V) -s $(SERIAL) make SERIAL=$(SERIAL) qemu-grade; \
		(test -f $(LABDIR)/.config.bak && cp $(LABDIR)/.config.bak $(LABDIR)/.config && rm $(LABDIR)/.config.bak) || :; \
	else \
		echo "[grade] Docker unavailable; running the official grader locally."; \
		echo "[grade] This still uses scores.json + expect.py + qemu-grade."; \
		$(MAKE) official-grade-local; \
	fi

doctor:
	$(Q)bash $(SCRIPTS)/doctor.sh

.PHONY: qemu qemu-gdb gdb defconfig build clean distclean grade official-grade-local doctor all
