"""python3 -m app：启动本地服务，手机用同一 Wi-Fi 打开。"""

import uvicorn

from .config import HOST, PORT, server_hint


def main() -> None:
    print(f"qpquiz-web 启动中：{server_hint(HOST, PORT)}")
    print(f"手机访问：http://<本机局域网 IP>:{PORT}")
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
