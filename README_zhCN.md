![演示](/demo/demo.gif)

# sd_extension-prompt_formatter
这是 [AUTOMATIC1111/stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui) 的扩展，它在提示旁边添加了一个魔术按钮，使其看起来整洁且“优化”。 它可以做几件事。
1. 将字符标准化为其标准等效字符（[NFKC](https://en.wikipedia.org/wiki/Unicode_equivalence#Normal_forms)）
2. 将括号标准化为其最小匹配对
3. 删除过多的空白
4. 正确使用空格、括号、逗号和“|”
5. 将嵌套括号 `((a))` 转换为单括号权重 `(a:1.21)`

适用于 txt2img 和 img2img，用于正面和负面提示。

*截至提交 54d57c2 v0.3 的当前情况，可能不考虑转义括号和方括号，并且可能会使扩展崩溃。*

**例子**

原始提示
````
帅气男性真实照片（巫师：1.2）， <lora:LuisapHotlineStyle:0.5> <lora:ElegantHanfuRuqunStyle:0.2> 短胡须，白色巫师衬衫，（金色镶边：0.8），（（（秃头））
````

格式化
````
英俊男性的逼真照片（巫师：1.2），<lora:LuisapHotlineStyle:0.5> <lora:ElegantHanfuRuqunStyle:0.2> 短胡子，白色巫师衬衫，（金色镶边：0.8），（秃头：1.21）
````

原始提示
````
a、[[b、[c、[A:B]、[A|B]、[A:1.2 和 B:1.2]]、e]]
````

格式化
````
a, (b, (c, [A:B], [A|B], [A:1.2 AND B:1.2]:0.91), e:0.83)
````


灵感来自 [canisminor1990/sd-webui-kitchen-theme](https://github.com/canisminor1990/sd-webui-kitchen-theme) 的提示格式化程序。

＃＃ 安装
1. 在 Stable Diffusion Web UI 中，导航至 **扩展** > **从 URL 安装**
2. 将此存储库复制并粘贴到 URL install

`https://github.com/uwidev/sd_extension-prompt_formatter`

3. 安装
4. 转到 **已安装** 选项卡并单击 **应用并重新启动 UI**

## 其他计划的（？）功能
- [x] 考虑[提示编辑](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Features#prompt-editing)（不要转换[from:to:when] ⏫ ✅ 2023 -04-27
- [x] 修复：不要将 {} 转换为 ()（通配符修复）⏫ ✅ 2023-04-27
- [x] 处理嵌套括号内的附加括号权重，例如 ((A), (B)) => ((A, B)) => (A, B:1.21) ✅ 2023-04-27
- [x] 以某种方式神奇地解决混合括号（例如像这样输入提示的“([<1girl>])”？！1） ✅ 2023-04-27 **可能已修复？**
- [ ] 创建新行（在 BREAK 上拆分提示时很有用）
- [ ] 进一步简化 `[(a:0.91)]` => `(a:0.83)`，而不是 `((a:0.91):0.91)`
- [ ] 一个“恢复”按钮，以防万一格式不正确（我的逻辑很奇怪）🔼
- [ ] 可以选择将网络移至后面，而不是始终强制执行。
- [x] 扩展设置菜单。
- [x] 将标记空格转换为下划线的选项
- [ ] 可以选择将多个加权标记块分成单独的块吗？ 例如 （A，B：1.2）=>（A：1.2），（B：1.2）
- [ ] 更新右上角的令牌计数器，使其在提示格式上不再呈红色（看起来需要学习 javascript）
- [ ] 将括号标准化为其最大匹配对的选项（例如 `(((a` -> `(((a)))`
- [x] 正确测试提示以加快开发速度 ✅ 2023-04-27