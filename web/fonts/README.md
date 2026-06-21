# 可选 Web 字体（LXGW 文楷 GB）

默认使用**系统字体**。若要在设置中选择「LXGW WenKai GB」，需先安装字体分片：

```powershell
# 项目根目录
.\scripts\install-web-fonts.ps1
```

脚本会从 npm 包 `lxgw-wenkai-gb-web` 复制 `result.css` 与 `.woff2` 到本目录。

未安装时选择霞鹜文楷会回退到系统字体，并在聊天区提示运行上述脚本。
