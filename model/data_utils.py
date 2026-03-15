# data_utils.py
import pandas as pd
import numpy as np
import torch
from torch_geometric.loader import DataLoader
from sklearn.model_selection import train_test_split
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors
#from smiles_to_graph_2 import getGraph  # 引用你现有的脚本

def extract_rdkit_global(smiles):
    """
    辅助函数：从 SMILES 提取 5 个关键的全局描述符
    """
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return [0.0] * 5
    return [
        Descriptors.MolWt(mol),            # 分子量 (MW)
        Descriptors.MolLogP(mol),          # 脂水分配系数 (LogP)
        rdMolDescriptors.CalcNumRings(mol),# 环的数量
        # 统计双键数量
        sum(1 for b in mol.GetBonds() if b.GetBondType() == Chem.rdchem.BondType.DOUBLE),
        rdMolDescriptors.CalcNumAromaticRings(mol) # 芳香环数量
    ]

def build_combined_dataset(df, label_col):
    """
    将 DataFrame 转换为 PyG 的 Dataset。
    1. 调用 getGraph 构建图结构。
    2. 注入全局特征 (HOMO, LUMO + 5个RDKit特征)。
    3. 注入目标标签 (y)。
    """
    dataset = []
    # 定义我们期望在 df 中找到的全局特征列名
    global_cols = ['HOMO', 'LUMO', 'MW', 'LogP', 'RingCount', 'DoubleBonds', 'AromaticRings']
    
    print(f"开始构建图数据集，目标列: {label_col}...")
    
    for _, row in df.iterrows():
        # 调用 smiles_to_graph.py 中的 getGraph 函数
        data = getGraph(row['SMILES'])
        
        if data is None:
            continue
            
        # 1. 准备全局特征 (形状为 [1, 7])
        extra_features = [row[col] for col in global_cols]
        data.global_feat = torch.tensor([extra_features], dtype=torch.float)
        
        # 2. 准备标签 y (形状为 [1, 1])
        data.y = torch.tensor([[row[label_col]]], dtype=torch.float)
        
        dataset.append(data)
        
    print(f"成功构建数据集，有效样本数: {len(dataset)}")
    return dataset

from smiles_to_graph_2 import getGraph    
def build_combined_dataset_v2(df, label_col, feature_cols):
    dataset = []
    for _, row in df.iterrows():
        data = getGraph(row['SMILES'])
        if data is None: continue
            
        # 提取 11 个特征
        extra_features = [row[col] for col in feature_cols]
        data.global_feat = torch.tensor([extra_features], dtype=torch.float)
        data.y = torch.tensor([[row[label_col]]], dtype=torch.float)
        dataset.append(data)
    return dataset


def get_train_val_loaders(dataset, batch_size=16, test_size=0.2, random_state=42):
    """
    划分数据集并返回三个 DataLoader：
    1. train_loader: 用于训练 (shuffle=True)
    2. test_loader: 用于测试评估 (shuffle=False)
    3. eval_train_loader: 用于实时监控训练集 R2 (shuffle=False)
    """
    train_data, test_data = train_test_split(
        dataset, 
        test_size=test_size, 
        random_state=random_state
    )
    
    train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_data, batch_size=batch_size, shuffle=False)
    eval_train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=False)
    
    return train_loader, test_loader, eval_train_loader