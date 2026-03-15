import torch
from torch_geometric.data import Data
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import RDLogger
import warnings
import numpy as np
import math

# 静默 RDKit 警告
RDLogger.DisableLog('rdApp.*')
warnings.filterwarnings("ignore")

# ==================== 原子特征 (升级为 25 维：共轭增强版) ====================
# H, C, N, O, F, P, S, Cl, Br, I
ALLOWED_ATOMS = [1, 6, 7, 8, 9, 15, 16, 17, 35, 53]  

# 预设电负性字典 (Pauling Scale)
ELECTRONEGATIVITY = {1: 2.20, 6: 2.55, 7: 3.04, 8: 3.44, 9: 3.98, 15: 2.19, 16: 2.58, 17: 3.16, 35: 2.96, 53: 2.66}

def atom_features(atom: Chem.Atom):
    """
    返回 25 维原子特征，增强共轭与电子环境描述
    """
    # 1-10: 原子类型 one-hot
    atom_type = [int(atom.GetAtomicNum() == n) for n in ALLOWED_ATOMS]

    # 11: 总度数 (0~5)
    degree = min(atom.GetTotalDegree(), 5)

    # 12: 形式电荷
    formal_charge = atom.GetFormalCharge()

    # 13-15: 杂化方式 one-hot
    hybridization = atom.GetHybridization()
    hyb_sp  = int(hybridization == Chem.rdchem.HybridizationType.SP)
    hyb_sp2 = int(hybridization == Chem.rdchem.HybridizationType.SP2)
    hyb_sp3 = int(hybridization == Chem.rdchem.HybridizationType.SP3)

    # 16: 是否在环中
    is_in_ring = int(atom.IsInRing())

    # 17: 是否为芳香原子 (共轭核心)
    aromatic = int(atom.GetIsAromatic())

    # 18: 原子质量 (归一化)
    mass = atom.GetMass() / 100.0

    # 19: 电负性 (归一化)
    en = ELECTRONEGATIVITY.get(atom.GetAtomicNum(), 2.0) / 4.0
    
    # 20: Gasteiger 部分电荷 (关键电子特征)
    # 默认值为 0，将在主函数中更新
    partial_charge = 0.0
    try:
        if atom.HasProp('_GasteigerCharge'):
            val = atom.GetProp('_GasteigerCharge')
            f_val = float(val)
            # 检查是否为 NaN 或无穷大
            if math.isnan(f_val) or math.isinf(f_val):
                partial_charge = 0.0
            else:
                partial_charge = f_val
        else:
            partial_charge = 0.0
    except:
        partial_charge = 0.0

    # --- 新增/增强特征 (21-25) ---
    
    # 21: Pi 电子数估算 (对共轭体系的直接贡献)
    # 芳香原子贡献 1 个，双键贡献 1 个
    n_pi = 0
    if aromatic: 
        n_pi = 1
    else:
        for b in atom.GetBonds():
            if b.GetBondType() == Chem.rdchem.BondType.DOUBLE:
                n_pi += 1
    
    # 22: 空间位阻度 (取代基拥挤度，影响共轭面平整度)
    # 非氢邻居数 / 4
    steric_bulk = float(atom.GetDegree()) / 4.0

    # 23: 5元环标记 (光电材料中常见的噻吩、吡咯等单元)
    is_5_ring = int(atom.IsInRingSize(5))
    
    # 24: 6元环标记 (苯环、吡啶等单元)
    is_6_ring = int(atom.IsInRingSize(6))

    # 25: 杂原子极性标记 (N, O, S 等对电荷转移的影响)
    is_hetero = int(atom.GetAtomicNum() in [7, 8, 16])

    return atom_type + [
        degree, formal_charge, hyb_sp, hyb_sp2, hyb_sp3,
        is_in_ring, aromatic, mass, en, partial_charge,
        n_pi, steric_bulk, is_5_ring, is_6_ring, is_hetero
    ]

# ==================== 边特征 (保持 6 维，增强共轭表达) ====================
def bond_features(bond: Chem.Bond):
    bt = bond.GetBondType()
    # 显式捕捉共轭状态
    is_conjugated = int(bond.GetIsConjugated())
    
    return [
        int(bt == Chem.rdchem.BondType.SINGLE),
        int(bt == Chem.rdchem.BondType.DOUBLE),
        int(bt == Chem.rdchem.BondType.AROMATIC),
        is_conjugated,  # 关键：是否处于共轭体系
        int(bond.IsInRing()),
        # 混合特征：芳香键且在共轭体系中赋予更高权重
        (is_conjugated * 0.5 + 0.5) if bt == Chem.rdchem.BondType.AROMATIC else 0.0
    ]

# ==================== 主函数 ====================
def getGraph(smiles: str) -> Data:
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None: return None

        # 1. 预处理
        # 必须先 Sanitise 以识别芳香性，但不要强制 Kekulize，否则会丢失芳香键特征
        Chem.SanitizeMol(mol)
        
        # 计算部分电荷 (Gasteiger)
        AllChem.ComputeGasteigerCharges(mol)

        # 2. 原子特征 (25维)
        atoms_feat = [atom_features(atom) for atom in mol.GetAtoms()]
        x = torch.tensor(atoms_feat, dtype=torch.float)

        # 3. 边特征 (双向)
        edge_index, edge_attr = [], []
        for bond in mol.GetBonds():
            i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
            feat = bond_features(bond)
            
            # 正向
            edge_index.append([i, j])
            edge_attr.append(feat)
            # 反向
            edge_index.append([j, i])
            edge_attr.append(feat)

        if len(edge_index) == 0:
            edge_index = torch.empty((2, 0), dtype=torch.long)
            edge_attr  = torch.empty((0, 6), dtype=torch.float)
        else:
            edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
            edge_attr  = torch.tensor(edge_attr, dtype=torch.float)

        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr)

    except Exception as e:
        # 如果是因为某些特殊分子的电荷计算失败，这里会捕获
        return None