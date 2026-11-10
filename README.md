# 通勤监控

工作日早上自动查询高德地图通勤时间，有迟到风险时微信提醒。

## 部署步骤

1. 在 GitHub 新建一个 **private** 仓库，把本目录全部文件推送上去
2. 进入仓库 **Settings → Secrets and variables → Actions**，添加以下 Secrets：

| Secret 名 | 值 |
|---|---|
| `AMAP_KEY` | 你的高德 Web 服务 Key |
| `SERVERCHAN_KEY` | 你的 Server酱 SendKey |
| `HOME_ADDRESS` | 家庭地址 |
| `COMPANY_ADDRESS` | 公司地址 |
| `HOME_CITY` | 家所在城市（如：太仓） |
| `COMPANY_CITY` | 公司所在城市（如：苏州） |

3. 推送后 Actions 会自动定时运行。也可在 **Actions → Commute Check → Run workflow** 手动触发测试。

## 定时规则

| 时间（北京时间） | 说明 |
|---|---|
| 7:40 / 7:45 / 7:50 / 7:55 | 查询路况，微信推送预计到达时间 |
| 8:00 | 最后一次查询 |

## 自定义

修改 `.github/workflows/commute-check.yml` 中的 `WORK_START_HOUR` / `BUFFER_MINUTES` 等环境变量即可。
