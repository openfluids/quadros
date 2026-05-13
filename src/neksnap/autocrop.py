import os
from PIL import Image

def crop_transparent_areas(folder_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".png"):
            image_path = os.path.join(folder_path, filename)
            try:
                with Image.open(image_path) as img:
                    # Ensure image has an alpha channel
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")
                    
                    # Get bounding box of non-transparent areas
                    alpha = img.split()[-1]  # Get the alpha channel
                    bbox = alpha.getbbox()
                    
                    if bbox:
                        cropped_img = img.crop(bbox)

                        # Save the cropped image
                        output_path = os.path.join(output_folder, filename)
                        cropped_img.save(output_path)

                        print(f"Cropped and saved: {filename}")
                    else:
                        print(f"Image {filename} is fully transparent, skipping.")
            except Exception as e:
                print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    input_folder = input("Enter the path to the folder containing PNG images: ").strip()
    output_folder = input("Enter the path to save cropped images: ").strip()

    crop_transparent_areas(input_folder, output_folder)
