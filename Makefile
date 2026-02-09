.PHONY: package clean

package:
	@./scripts/build_ankiaddon.sh

clean:
	@rm -rf dist
