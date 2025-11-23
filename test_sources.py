import asyncio
from main import app, verify_content_agent

async def main():
    async with app.run() as agent_app:
        result = await verify_content_agent(
            url="https://www.nytimes.com/2025/11/20/health/vaccine-autism-cdc-website.html",
            title="C.D.C. Website No Longer Rejects Possible Link Between Autism and Vaccines",
            subtext="NYT article about CDC website update",
            postDate="2025-11-20T12:00:00Z",
            app_ctx=agent_app.context,
        )
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
