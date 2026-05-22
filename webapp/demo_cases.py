"""
ATLAS Webapp — Predefined demo cases.
Three carefully chosen examples that showcase different ATLAS capabilities.
"""

DEMO_CASES = {
    "cd8_t_cell": {
        "label": "🛡️ CD8+ T cell (clean case)",
        "description": "A textbook PBMC cluster. Shows ATLAS handling well-defined cell types at maximum confidence (Score ~92).",
        "species": "Human",
        "tissue": "PBMC",
        "additional_info": "Healthy donor peripheral blood mononuclear cells, well-defined cluster.",
        "markers": [
            "CD8A", "CD8B", "CD3D", "CD3E", "CD3G",
            "GZMK", "GZMA", "NKG7", "CCL5", "CST7",
            "IL7R", "CD2", "LCK", "ITM2A", "PRF1",
            "TRAC", "TRBC1", "TRBC2", "LTB", "CXCR4",
        ],
        "expected_celltype": "CD8+ T cells",
        "expected_score_range": (85, 100),
    },

    "plasma_cell_trap": {
        "label": "🧬 Plasma cell (housekeeping-dominated)",
        "description": "A challenging case where top markers are housekeeping genes (GAPDH, ACTB). Tests if ATLAS can see past noise.",
        "species": "Human",
        "tissue": "Bone marrow",
        "additional_info": "Bone marrow sample with suspected antibody-producing cell cluster.",
        "markers": [
            "GAPDH", "ACTB", "B2M", "HSP90AA1", "HSPA8",
            "EEF1A1", "PPIA", "PFN1", "TPT1", "UBA52",
            "IGHG1", "IGHG3", "IGKC", "MZB1", "XBP1",
            "JCHAIN", "PRDM1", "IRF4", "SDC1", "CD38",
        ],
        "expected_celltype": "Plasma cells",
        "expected_score_range": (70, 90),
    },

    "fig6b_schwann": {
        "label": "🔬 Paper Fig 6b: Gold-standard error",
        "description": "The famous case from CASSIA paper: a cluster labeled 'monocyte' but markers indicate enteric glial cells. Demonstrates error detection.",
        "species": "Human",
        "tissue": "Large intestine",
        "additional_info": "Cluster was annotated as 'monocyte' in the reference, but please re-examine carefully.",
        "markers": [
            "NKAIN3", "SPP1", "CDH19", "TSPAN11", "PLP1",
            "L1CAM", "MYOT", "IGSF11", "NRXN1", "SLC35F1",
            "SFRP5", "SOX10", "MEGF10", "SYT10", "CADM2",
            "SLITRK2", "SOX2", "CRTAC1", "CHL1", "ZNF536",
        ],
        "expected_celltype": "Enteric glial / Schwann cells (NOT monocytes!)",
        "expected_score_range": (55, 75),
    },
}
