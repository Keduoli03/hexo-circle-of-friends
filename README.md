# RSS Circle（友链朋友圈）

你是否经常烦恼于友链过多但没有时间浏览？那么 RSS Circle（友链朋友圈）将解决这一痛点。你可以随时获取友链网站的更新内容，并了解友链的活跃情况。

> 本项目是基于 [hexo-circle-of-friends](https://github.com/Rock-Candy-Tea/hexo-circle-of-friends)（原作者 [Rock-Candy-Tea](https://github.com/Rock-Candy-Tea)）的**二改版本**，由 [Keduoli03](https://github.com/Keduoli03) 在原项目基础上做了少量改动，并更名为 `rss_circle`。定位为通用的友链朋友圈服务，不再局限于 Hexo 博客。

即日起，项目恢复更新和维护，发布`v6.x.x`版本。

部署教程：[文档](https://fcircle-doc.yyyzyyyz.cn/)

### `v6.0.6` 更新说明：

- 🐛 **修复 `/all` 接口分页 bug**：修复 end=-1 时 `$limit` 传入负数导致 MongoDB 报错的问题
- 🐛 **修复 `/post` 接口换域名问题**：友链博主更换域名（且老域名重定向）后，老的 link 仍能查询到对应文章
- 🐛 **修复 MongoDB 集合名不一致**：统一 Rust core 与 Python API 的集合名为 `Post`/`Friend`（单数）
  - ⚠️ MongoDB 用户升级后，下一次定时任务运行后会自动重新填充数据；原 `Posts`/`Friends` 集合可手动删除
- 🐛 **修复 feed 日期解析**：当 `published`/`updated` 缺失时互相 fallback，避免文章日期显示为爬取当天
- 🚀 **性能优化**：mongodbapi 中 `last_updated_time` 查询改用 `find_one + sort` 替代 `limit(1000) + max()`

[![Stargazers over time](https://starchart.cc/Keduoli03/rss_circle.svg)](https://starchart.cc/Keduoli03/rss_circle)
