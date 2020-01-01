version := $(shell ./setup.py --version)
name := $(shell ./setup.py --name)

src := $(shell find zerowire -name '*.py') setup.py $(wildcard scripts/*)
dst := $(addprefix build/,$(src)) build/requirements.txt build/README.md
whl := $(name)-$(version)-py3-none-any.whl
exe := zerowire.pyz

pyz: $(exe)

wheel: $(whl)

$(whl): $(dst)
	cd build; python3 setup.py bdist_wheel -d ../

$(exe): build/pkg
	cd build; python3 -m zipapp \
		-p "/usr/bin/env python3" \
		pkg \
		-m zerowire.__main__:main -o ../zerowire.pyz
	chmod og-r $@

build/pkg: $(whl)
	chmod +x build/setup.py
	mkdir -p $@
	python3 -m pip install -r build/requirements.txt --target $@ --upgrade
	python3 -m pip install $(whl) --target $@ --upgrade

build/requirements.txt: requirements.txt
	grep -v dbus_python $< > $@

build/README.md: README.md
	cp $< $@

build/%.py: %.py
	@mkdir -p $(dir $@)
	@echo "[strip-hints] $< $@"
	@strip-hints $< > $@

build/scripts/%: scripts/%
	mkdir -p build/scripts
	cp $< $@

clean:
	rm -rf build zerowire.pyz

.PHONY: install build clean
