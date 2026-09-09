import json
import os
import shutil
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

templates = defaultdict(dict)
conditions: dict[str, list[dict]] = defaultdict(list)

templates_dir = Path(__file__).parent.joinpath("templates")
templates_dir_path = str(templates_dir.absolute())


for json_file in templates_dir.iterdir():
    if not json_file.name.endswith(".json"):
        continue
    data = json.loads(json_file.read_text("utf8"))
    for image in data.values():
        image_file_name: str = image["filename"]
        assert image_file_name.endswith(".png")
        image_name = image_file_name[:-4]
        for region in image["regions"]:
            region_name = region["region_attributes"]["name"].strip()
            box = [
                region["shape_attributes"]["x"],
                region["shape_attributes"]["y"],
                region["shape_attributes"]["x"] + region["shape_attributes"]["width"],
                region["shape_attributes"]["y"] + region["shape_attributes"]["height"],
            ]
            region_conditions = region["region_attributes"].get("conditions", "")
            if region_conditions != "":
                region_conditions = region_conditions.split(",")
            else:
                region_conditions = []
            template_info = {
                "template_name": f"{image_name}--{region_name}",
                "image_name": image_name,
                "region_name": region_name,
                "box": box,
                "left": box[0],
                "top": box[1],
                "right": box[2],
                "bottom": box[3],
                "width": box[2] - box[0],
                "height": box[3] - box[1],
                "center": [(box[0] + box[2]) // 2, (box[1] + box[3]) // 2],
                "conditions": region_conditions,
            }
            for cond in region_conditions:
                conditions[cond].append(template_info)
            templates[image_name][region_name] = template_info


def draw_label(draw: ImageDraw.ImageDraw, pos: tuple[int, int], text: str, color="red"):
    imw, imh = draw._image.size
    base_size = 8
    font_size = 6 * base_size
    padding = base_size
    padding_v = base_size
    padding_h = 4 * base_size
    radius = base_size
    gap = 2 * base_size
    min_margin = 2 * base_size
    font = ImageFont.load_default(font_size)
    ascent, descent = font.getmetrics()  # type: ignore
    draw_text_params = {
        "text": text,
        "font": font,
        "anchor": "ls",
    }
    text_pos = [pos[0] + padding_h, pos[1] - gap - padding_v - descent]
    bbox = draw.textbbox(xy=tuple(text_pos), **draw_text_params)

    bg_bbox = [
        pos[0],
        pos[1] - gap - padding_v - font_size - gap,
        bbox[2] + padding_h,
        pos[1] - gap,
    ]
    right_margin = imw - min_margin - bg_bbox[2]
    if right_margin < 0:
        text_pos[0] += right_margin
        bg_bbox[0] += right_margin
        bg_bbox[2] += right_margin
    draw.rounded_rectangle(
        bg_bbox,
        fill="white",
        radius=radius,
    )
    draw.text(
        xy=tuple(text_pos),
        **draw_text_params,
        fill=color,
    )
    return bg_bbox


def generate_preview():
    preview_dir = templates_dir_path + "/" + "templates-preview"
    shutil.rmtree(preview_dir, ignore_errors=True)
    os.makedirs(preview_dir)
    for img_name, regions in templates.items():
        for region_name, info in regions.items():
            img = Image.open(templates_dir_path + "/" + img_name + ".png")
            draw = ImageDraw.Draw(img)
            box = info["box"]
            draw.rectangle(box, outline="red", width=3)
            bg_bbox = draw_label(draw, (box[0], box[1]), region_name)
            for cond in info["conditions"]:
                bg_bbox = draw_label(
                    draw, (box[0], bg_bbox[1]), "condition: " + cond, color="black"
                )
            img.save(f"{preview_dir}/{img_name}--{region_name}.png")
    condition_keys = list(conditions.keys())
    condition_keys.sort()
    preview_conditions = {}
    for key in condition_keys:
        preview_conditions[key] = " && ".join(
            [x["template_name"] for x in conditions[key]]
        )
    Path(f"{preview_dir}/conditions.json").write_text(
        json.dumps(preview_conditions, indent=2)
    )


def get_template_info(template_name: str):
    file_name, region_name = template_name.split("--")
    return templates[file_name][region_name]


def match_single_template(image_path: str, template_name: str):
    file_name, region_name = template_name.split("--")
    region_box = templates[file_name][region_name]["box"]
    template_image_path = f"{templates_dir_path}/{file_name}.png"
    with Image.open(template_image_path) as template_image, Image.open(
        image_path
    ) as image:
        assert template_image.size == image.size
        target_region = image.crop(region_box).convert("RGB")
        template_region = template_image.crop(region_box).convert("RGB")
        diff = np.array(ImageChops.difference(target_region, template_region))
        diff_ratio = np.mean(diff > 10)
        return bool(diff_ratio < 0.005)


def match_templates(image_path: str, templates: list[str]):
    match_result = {}
    for template in templates:
        match_result[template] = match_single_template(image_path, template)
    return match_result


def match_condition(image_path: str, condition: str):
    templates = conditions.get(condition)
    if not templates:
        return False
    return all(
        [match_single_template(image_path, x["template_name"]) for x in templates]
    )


async def get_button_pos(image_path: str, button_template_name: str):
    assert match_single_template(image_path, button_template_name)
    info = get_template_info(button_template_name)
    center = info["center"]
    return center


if __name__ == "__main__":
    generate_preview()
