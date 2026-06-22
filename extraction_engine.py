import os
from paddleocr import PaddleOCR

def run_extraction():
    print("[INFO] Initializing Step 5: OCR Engine (Stable CPU Mode)...")
    
    # use_gpu=False karne se cudnn64_8.dll ka error khatam ho jayega
    ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)

    image_path = "vision_ready.jpg"
    
    if not os.path.exists(image_path):
        print(f"[ERROR] '{image_path}' nahi mili!")
        return

    print(f"[INFO] Extracting text... Please wait.")
    result = ocr.ocr(image_path, cls=True)

    if result and result[0]:
        extracted_lines = [line[1][0] for line in result[0]]
        
        print("\n" + "="*50)
        for text in extracted_lines:
            print(f"-> {text}")
            
        with open("raw_text.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(extracted_lines))
        
        print("="*50)
        print(f"[SUCCESS] Data saved to raw_text.txt")

if __name__ == "__main__":
    run_extraction()