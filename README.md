# Mobility Prediction for Organic Conductive Polymers

This repository contains the code, data, and experiment pipeline for my master's thesis on **charge mobility prediction of organic conductive polymers** using **graph neural networks, feature fusion, and interpretable machine learning**.

The project focuses on building a high-quality literature-derived dataset and developing predictive models for **hole mobility** and **electron mobility** of conjugated/organic conductive polymers. Polymer repeat units are represented as parsable **SMILES**, and the prediction framework combines **structural representations**, **electronic-structure descriptors**, **polymer-scale priors**, and **custom proxy descriptors** for small-data learning. The overall study includes dataset construction, model benchmarking, feature-fusion experiments, residual analysis, and SHAP-based interpretation. 

---

## Overview

Charge transport in organic conductive polymers is jointly affected by molecular structure, side-chain design, polymer packing, morphology, and processing conditions. Because these factors are strongly coupled across multiple scales, predicting mobility from structure alone is challenging. This project addresses that problem with a data-driven workflow that integrates:

- literature-based data collection and cleaning
- human-in-the-loop extraction of polymer structures and physical parameters
- graph neural network models and conventional machine learning baselines
- progressive feature fusion for improved prediction in small-data settings
- interpretability analysis for understanding key factors behind mobility variation

According to the thesis design, the project includes a dedicated database construction workflow, a unified mobility prediction benchmark, and an interpretation stage based on residual analysis and SHAP.

---

## Main Contributions

- Built a curated dataset for **organic conductive polymers** from peer-reviewed literature.
- Established two regression tasks:
  - **hole mobility prediction**
  - **electron mobility prediction**
- Developed and compared five representative models:
  - self-developed **MPNN**
  - **NNConv-MPNN**
  - **Chemprop / D-MPNN**
  - **Random Forest**
  - **XGBoost**
- Designed three progressive input settings:
  - **Configuration A**: structural representation only
  - **Configuration B**: structure + electronic-structure descriptors + polymer-scale priors
  - **Configuration C**: Configuration B + 7 custom proxy descriptors
- Conducted residual analysis, long-tail sample analysis, and SHAP-based interpretation to explain model behavior and feature importance. 

---

## Dataset

The dataset was constructed from published journal articles through a human-machine collaborative pipeline. The workflow includes:

1. literature collection and screening
2. extraction of text-based parameters using LLM-assisted methods
3. structure acquisition from molecular images with tool-assisted recognition and manual verification
4. digital reconstruction and standardization of polymer repeat units
5. data cleaning, consistency checking, and structured storage

Polymer repeat units are represented as **SMILES**, and the target variable is the **maximum field-effect mobility** reported in the literature for each material. Two prediction tasks are defined accordingly: hole mobility and electron mobility. The thesis also reports a final curated dataset with **983 records**, including **826 valid samples for hole mobility** and **625 valid samples for electron mobility**. 

> **Note**
> The dataset included in this repository may be a processed/reorganized version for reproducibility. Please refer to the original thesis for the full curation protocol and data-screening criteria.

---

## Environment

- Python 3.10
- PyTorch 2.x
- PyTorch Geometric
- RDKit
- Chemprop
- Lightning
- scikit-learn
- pandas
- numpy

---

## Installation

requirements.txt
