default: zwift_workout_file_tag_reference.md

PYTHON_FILES = $(shell find zwift_zwo_docs -name '*.py')

zwift_workout_file_tag_reference.md: $(PYTHON_FILES) descriptions.yaml tag_attr_usage.json
	zwift-zwo-docs-render tag_attr_usage.json descriptions.yaml > zwift_workout_file_tag_reference.md

tag_attr_usage.json: $(wildcard workouts)
	zwift-zwo-docs-analyse --json $< > tag_attr_usage.json

clean-md: $(wildcard zwift_workout_file_tag_reference.md)
	rm -f $<

clean-json: $(wildcard tag_attr_usage.json)
	rm -f $<

clean-all: clean-md clean-json

.PHONY: clean-all clean-md clean-json
