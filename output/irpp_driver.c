/*
 * irpp_driver.c — Calculette IRPP 2023, pilote simplifié
 *
 * Entrée (stdin) : lignes KEY=VALUE (variables formulaire 2042)
 * Sortie (stdout): résultats clé=valeur JSON-friendly
 *
 * Compilation (WSL) :
 *   CDRIVER=../mlang-src/examples/dgfip_c/ml_primitif/c_driver
 *   cd /mnt/f/Claude/impots/output
 *   gcc -std=c99 -O1 -I. irpp_driver.c mlang.c varinfos.c varinfo_0.c \
 *     varinfo_1.c varinfo_2.c varinfo_3.c varinfo_4.c varinfo_5.c \
 *     varinfo_6.c varinfo_7.c varinfo_8.c \
 *     m_main.c m_cibles.c m_chap-*.c m_codes_1731.c m_commence_par_5.c \
 *     m_commence_par_7.c m_commence_par_H.c m_correctif.c m_horizoc.c \
 *     m_horizoi.c m_res-ser1.c m_res-ser2.c m_coc1.c m_coc2.c m_coc3.c \
 *     m_coc4.c m_coc5.c m_coc7.c m_coi1.c m_coi2.c m_coi3.c \
 *     compir_contexte.c compir_famille.c compir_penalite.c compir_restitue.c \
 *     compir_revcor.c compir_revenu.c compir_tableg.c compir_tableg01.c \
 *     compir_tableg02.c compir_tableg03.c compir_tableg04.c compir_tablev.c \
 *     compir_variatio.c erreurs.c irpp_2023.c \
 *     $CDRIVER/irdata.c \
 *     -o irpp_calc -lm
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mlang.h"

/* Variables de sortie à restituer */
static const char *OUTPUT_VARS[] = {
    "IINET",    /* Impôt net final (après décote, réductions, crédits) */
    "IRNET",    /* IR net avant crédits */
    "NBPT",     /* Nombre de parts fiscales */
    "RNI",      /* Revenu net imposable */
    "REVKIRE",  /* Revenu fiscal de référence */
    "IAVIM",    /* Impôt avant imputation réductions/crédits */
    "IRTOTAL",  /* IR total foyer */
    NULL
};

static void set_var(T_irdata *irdata, const char *name, double val) {
    T_varinfo *vi = cherche_varinfo(irdata, name);
    if (vi != NULL) {
        ecris_varinfo(irdata, ESPACE_PAR_DEFAUT, vi, 1, val);
    }
}

int main(void) {
    T_irdata *irdata;
    char line[512];
    int i;

    irdata = cree_irdata();
    if (irdata == NULL) {
        fprintf(stderr, "ERREUR: impossible d'allouer irdata\n");
        return 1;
    }

    /* Lecture des variables d'entrée depuis stdin */
    while (fgets(line, sizeof(line), stdin)) {
        char *eq;
        char key[128];
        double val;
        size_t klen;

        /* Ignorer lignes vides et commentaires */
        if (line[0] == '\n' || line[0] == '#') continue;

        eq = strchr(line, '=');
        if (eq == NULL) continue;

        klen = (size_t)(eq - line);
        if (klen == 0 || klen >= sizeof(key)) continue;

        memcpy(key, line, klen);
        key[klen] = '\0';
        val = atof(eq + 1);

        set_var(irdata, key, val);
    }

    /* Variables système obligatoires (ne pas permettre override depuis stdin) */
    set_var(irdata, "ANCSDED", 2023.0);
    set_var(irdata, "V_MILLESIME", 2023.0);

    /* Lancement du calcul */
    enchainement_primitif_interpreteur(irdata);

    /* Restitution des résultats — JSON valide sans trailing comma */
    {
        static double vals[16];
        static const char *names[16];
        int n = 0;

        for (i = 0; OUTPUT_VARS[i] != NULL; i++) {
            T_varinfo *vi = cherche_varinfo(irdata, OUTPUT_VARS[i]);
            if (vi != NULL) {
                char def = 0;
                double val = 0.0;
                lis_varinfo(irdata, ESPACE_PAR_DEFAUT, vi, &def, &val);
                names[n] = OUTPUT_VARS[i];
                vals[n] = def ? val : 0.0;
                n++;
            }
        }

        printf("{\n");
        for (i = 0; i < n; i++) {
            printf("  \"%s\": %.2f%s\n", names[i], vals[i], i < n - 1 ? "," : "");
        }
        printf("}\n");
    }

    detruis_irdata(irdata);
    return 0;
}
