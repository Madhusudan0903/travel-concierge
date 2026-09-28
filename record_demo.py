import asyncio
import os
import shutil
import time
from playwright.async_api import async_playwright

ARTIFACT_DIR = "/config/.gemini/antigravity/brain/12bbece7-ade6-40c0-b065-55824cd3037d"
TEMP_VIDEO_DIR = "/tmp/playwright_videos"
FRONTEND_URL = "https://travel-concierge-frontend-480100122974.us-east1.run.app"

async def main():
    if os.path.exists(TEMP_VIDEO_DIR):
        shutil.rmtree(TEMP_VIDEO_DIR)
    os.makedirs(TEMP_VIDEO_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/google-chrome",
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=TEMP_VIDEO_DIR,
            record_video_size={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        print(f"Navigating to {FRONTEND_URL}...")
        await page.goto(FRONTEND_URL, wait_until="networkidle")
        await asyncio.sleep(2)

        # 1. First Prompt: What app does best (Destination search with dietary/airport memory context)
        print("Executing Prompt 1: Click prompt chip 'Destinations from DEL'...")
        chip = page.locator(".prompt-chip", has_text="Destinations from DEL")
        if await chip.count() > 0:
            await chip.first.click()
        else:
            await page.fill("#input", "Suggest vegetarian-friendly travel destinations from DEL")
            await page.click("button[type='submit']")

        # Wait for agent response to appear
        print("Waiting for response 1...")
        await asyncio.sleep(10)

        # 2. Second Richer Prompt: Multi-tool query (Currency conversion + Weather lookup)
        richer_prompt = "Convert 50,000 INR to JPY for my trip and tell me the weather in Tokyo"
        print(f"Executing Prompt 2: {richer_prompt}")
        await page.fill("#input", richer_prompt)
        await asyncio.sleep(1)
        await page.click("button[type='submit']")

        print("Waiting for response 2...")
        await asyncio.sleep(12)

        await context.close()
        await browser.close()
        print("Browser session closed. Video recording saved.")

    # Locate saved webm file
    video_files = [f for f in os.listdir(TEMP_VIDEO_DIR) if f.endswith(".webm")]
    if video_files:
        src_path = os.path.join(TEMP_VIDEO_DIR, video_files[0])
        dest_webm = os.path.join(ARTIFACT_DIR, "demo_video.webm")
        dest_mp4 = os.path.join(ARTIFACT_DIR, "demo_video.mp4")
        shutil.copy(src_path, dest_webm)
        print(f"Copied webm video to: {dest_webm}")

        # Convert webm to mp4 using ffmpeg if available
        ret = os.system(f"ffmpeg -y -i '{dest_webm}' -c:v libx264 -preset fast -crf 22 '{dest_mp4}'")
        if ret == 0 and os.path.exists(dest_mp4):
            print(f"Converted mp4 video saved to: {dest_mp4}")
        else:
            print(f"Using webm artifact: {dest_webm}")

if __name__ == "__main__":
    asyncio.run(main())
