import asyncio
import sys

# Import the classifier functions we already built
from services.classifier import classify, warmup

async def main():
    print("\n⏳ Loading propaganda classification model... (this may take a few seconds)")
    warmup()
    print("✅ Model loaded successfully!")
    print("=" * 60)
    print("Type your text below and hit ENTER. Press Ctrl+C to quit.")
    print("=" * 60)
    
    while True:
        try:
            text = input("\nEnter text to check:\n> ")
            if not text.strip():
                continue
            
            print("🔍 Analyzing...")
            result = await classify(text)
            
            print("\n" + "─" * 40)
            print("📊 SCORING RESULTS:")
            print("─" * 40)
            print(result)
            print("─" * 40)
            
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Exiting test program...")
            break

if __name__ == "__main__":
    asyncio.run(main())
