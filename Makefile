PYTHON ?= python
CONFIG ?= configs/default.yaml
OUTPUT_DIR ?= outputs

.PHONY: help run gui batch-ber gnuradio vehicular student-cases test compile

help:
	@echo "Available targets:"
	@echo "  make run         - Run the default Python-only simulation"
	@echo "  make gui         - Launch the PyQt dashboard"
	@echo "  make batch-ber   - Run BER vs SNR batch experiment"
	@echo "  make gnuradio    - Run with GNU Radio loopback override"
	@echo "  make vehicular   - Run the harsher vehicular scenario"
	@echo "  make student-cases - Run curated teaching-oriented testcases"
	@echo "  make test        - Run pytest"
	@echo "  make compile     - Compile all Python files"

run:
	$(PYTHON) main.py --config $(CONFIG)

gui:
	$(PYTHON) main.py --config $(CONFIG) --gui

batch-ber:
	$(PYTHON) run_experiments.py --experiment ber_vs_snr --config $(CONFIG) --output-dir $(OUTPUT_DIR)

gnuradio:
	$(PYTHON) main.py --config $(CONFIG) --override configs/scenario_gnuradio.yaml

vehicular:
	$(PYTHON) main.py --config $(CONFIG) --override configs/scenario_vehicular.yaml

student-cases:
	$(PYTHON) run_student_testcases.py --config $(CONFIG) --output-dir outputs/student_testcases

test:
	$(PYTHON) -m pytest tests -q

compile:
	$(PYTHON) -m compileall .
