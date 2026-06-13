STUDENT_ID ?= 
SSH_PORT ?= 50000
SUBMISSION_DIR ?= submissions
PUBLIC_MANIFEST ?= bank/public-manifest.json
DISK ?= bank/repair-fs-$(STUDENT_ID).qcow2
ISO ?= systemrescue-13.00-amd64.iso
SUBMIT_ZIP ?= submission-$(STUDENT_ID).zip

.PHONY: grade run submit clean-submit

grade:
	@if [ -z "$(STUDENT_ID)" ]; then echo "error: set STUDENT_ID=12_digit_id"; exit 2; fi
	python3 tools/grade_submission.py \
		--student-id "$(STUDENT_ID)" \
		--submission-dir "$(SUBMISSION_DIR)" \
		--manifest "$(PUBLIC_MANIFEST)"

run:
	@if [ -z "$(STUDENT_ID)" ]; then echo "error: set STUDENT_ID=12_digit_id"; exit 2; fi
	scripts/launch_qemu.sh --iso "$(ISO)" --disk "$(DISK)" --ssh-port "$(SSH_PORT)"

submit:
	@if [ -z "$(STUDENT_ID)" ]; then echo "error: set STUDENT_ID=12_digit_id"; exit 2; fi
	zip -r "$(SUBMIT_ZIP)" "$(SUBMISSION_DIR)"
	@echo "created $(SUBMIT_ZIP)"

clean-submit:
	rm -f submission-*.zip
