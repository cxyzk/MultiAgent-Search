import uvicorn
from app.agent.llm import run_agent

def run_loop():
    while(True):
        message=input("请输入你的问题")
        print(run_agent(message))


# if __name__ == "__main__":
#     run_loop()

if __name__ == '__main__':
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001,reload=True)
