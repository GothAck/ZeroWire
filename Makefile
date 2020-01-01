version := $(shell ./setup.py --version)
name := $(shell ./setup.py --name)

src := $(shell find zerowire -name '*.py') setup.py $(wildcard scripts/*)
dst := $(addprefix build/,$(src)) build/requirements.txt build/README.md
whl := $(name)-$(version)-py3-none-any.whl
deb := zerowire_$(version).deb
exe := zerowire.pyz

pyz: $(exe)

wheel: $(whl)

deb: $(deb)

$(whl): $(dst)
	cd build; python3 setup.py bdist_wheel -d ../

$(exe): build/pkg
	cd build; python3 -m zipapp \
		-p "/usr/bin/env python3" \
		pkg \
		-m zerowire.__main__:main -o ../zerowire.pyz
	chmod og-r $@

$(deb): $(exe)
	mkdir -p build/zerowire_$(version)/usr/local/bin
	mkdir -p build/zerowire_$(version)/lib/systemd/system
	mkdir -p build/zerowire_$(version)/DEBIAN
	cp zerowire.pyz build/zerowire_$(version)/usr/local/bin/zerowire
	cp -r systemd/* build/zerowire_$(version)/lib/systemd/system
	./debianize.py > build/zerowire_$(version)/DEBIAN/control
	cd build; dpkg-deb --build --root-owner-group zerowire_$(version) ../$@

clean:
	rm -rf build zerowire.pyz $(deb)

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

.PHONY: install build clean deb
