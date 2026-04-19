# Compile irpp_calc from Mlang-generated C files
# Run from this directory after step 3 (mlang code generation)
#
# Usage:
#   make CDRIVER=/path/to/mlang-src/examples/dgfip_c/ml_primitif/c_driver

CC     := gcc
CFLAGS := -std=c99 -O1 -I.

MLANG_C := mlang.c varinfos.c $(wildcard varinfo_*.c) \
           m_main.c m_cibles.c $(wildcard m_chap-*.c) \
           $(wildcard m_codes_*.c) $(wildcard m_commence_par_*.c) \
           m_correctif.c $(wildcard m_horizoc.c) $(wildcard m_horizoi.c) \
           $(wildcard m_res-ser*.c) $(wildcard m_coc*.c) $(wildcard m_coi*.c) \
           $(wildcard compir_*.c) erreurs.c irpp_2023.c

SRCS := irpp_driver.c $(MLANG_C)

.PHONY: all clean test

all: irpp_calc

irpp_calc: $(SRCS)
	@test -n "$(CDRIVER)" || \
	  (echo "❌  Définir CDRIVER : make CDRIVER=/path/to/mlang-src/examples/dgfip_c/ml_primitif/c_driver" && exit 1)
	$(CC) $(CFLAGS) $(SRCS) $(CDRIVER)/irdata.c -o $@ -lm
	@echo "✅  irpp_calc compilé"

test: irpp_calc
	@printf "V_0AC=1\nTSHALLOV=50000.00\n" | ./irpp_calc

clean:
	rm -f irpp_calc
