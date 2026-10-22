# AI 职业规划智能体登录模块

当前目录是登录模块成果目录，包含 Spring Boot 后端和 Vue3 前端。

## 项目结构

```txt
career-ai-codex-ready/
├─ backend-springboot/      Java Spring Boot + MyBatis + MySQL 后端
├─ frontend-vue3/           Vue3 登录/注册页面
├─ docs/
│  └─ LOGIN_MODULE_GUIDE.md 运行说明和接口说明
├─ start-login-module.ps1   一键启动脚本
└─ 启动登录模块.bat          双击启动入口
```

## 已实现功能

- 登录
- 注册
- MySQL 用户表
- MyBatis 数据库访问
- BCrypt 密码加密
- Vue3 前端登录/注册页面
- 4 位字母数字图形验证码
- CSS 验证码干扰效果

## 默认账号

```txt
用户名：demo
密码：demo123
```

## 启动方式

双击：

```txt
启动登录模块.bat
```

或手动启动：

```powershell
cd backend-springboot
.\mvnw.cmd spring-boot:run
```

```powershell
cd frontend-vue3
npm install
npm run dev
```

访问：

```txt
http://localhost:5173
```

详细说明见：

```txt
docs/LOGIN_MODULE_GUIDE.md
```
