# arXiv 查询词参考

## 核心原则

**只写材料体系名称，不加方法或物理量关键词。**

arXiv 按相关性排序，计算材料学论文本身就会包含 DFT/HSE/VASP 等词，
额外添加反而会过度限制结果，漏掉以不同术语描述同一方法的论文。

---

## 化学式写法规范

| 情况 | 推荐写法 | 不推荐 |
|------|---------|--------|
| 单一化合物 | `"SrTiO3"` | `"SrTiO3" HSE06 band gap VASP` |
| 同族材料 | `"perovskite oxide"` | `perovskite DFT+U Hubbard U value` |
| 二维材料 | `"MoS2 monolayer"` | `"MoS2" band gap experimental optical` |
| 锂电材料 | `"LiCoO2"` | `"LiCoO2" DFT+U Hubbard U` |
| 稀土化合物 | `"CeO2"` | `"CeO2" f-electron DFT+U` |

仅在化学式本身存在歧义（如区分体相与单层）时，才加一个限定词。

---

## 常见材料体系查询词

| 材料类型 | 查询词示例 |
|---------|-----------|
| 钛酸盐钙钛矿 | `"BaTiO3"` / `"SrTiO3"` / `"PbTiO3"` |
| 铁基钙钛矿 | `"BiFeO3"` / `"LaFeO3"` |
| 卤化物钙钛矿 | `"MAPbI3"` / `"CsPbBr3"` |
| 过渡金属氧化物 | `"TiO2"` / `"VO2"` / `"Fe2O3"` |
| 二维材料 | `"MoS2 monolayer"` / `"WSe2 monolayer"` / `"hBN monolayer"` |
| 锂电正极 | `"LiCoO2"` / `"LiFePO4"` / `"LiMn2O4"` |
| 拓扑材料 | `"Bi2Se3"` / `"Bi2Te3"` |
| 稀土氧化物 | `"CeO2"` / `"La2O3"` |
| 磁性材料 | `"NiO"` / `"MnO"` / `"CoO"` |
| III-V 半导体 | `"GaAs"` / `"InP"` / `"GaN"` |
| II-VI 半导体 | `"ZnO"` / `"CdS"` / `"ZnSe"` |

---

## 搜索结果不理想时的调整策略

1. 化学式换为矿物名：`"rutile"` 代替 `"TiO2"`
2. 换为上位类别：`"transition metal dichalcogenide"` 代替 `"MoS2"`
3. 尝试不加引号：`SrTiO3`（允许词语被拆分匹配）
4. 最多尝试 2 次调整后转为网络搜索
