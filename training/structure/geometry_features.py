import math

def compute_spatial_features(bbox_i, bbox_j, page_w, page_h):
    """
    Computes 12-dimensional normalized spatial-relational feature vector:
    1-4: Normalized coordinates of bbox_i: [xmin/W, ymin/H, xmax/W, ymax/H]
    5-8: Normalized coordinates of bbox_j: [xmin/W, ymin/H, xmax/W, ymax/H]
    9: Normalized horizontal center offset: delta_x = (cx_j - cx_i) / W
    10: Normalized vertical center offset: delta_y = (cy_j - cy_i) / H
    11: Normalized Euclidean distance: sqrt(delta_x^2 + delta_y^2)
    12: Direction angle theta = arctan2(delta_y, delta_x) / pi in [-1.0, 1.0]
    13: Intersection over Union (IoU)
    14: Aspect ratio difference log(w_i / w_j)
    15: Aspect ratio difference log(h_i / h_j)
    """
    w_i = max(1.0, bbox_i[2] - bbox_i[0])
    h_i = max(1.0, bbox_i[3] - bbox_i[1])
    cx_i = bbox_i[0] + w_i / 2.0
    cy_i = bbox_i[1] + h_i / 2.0

    w_j = max(1.0, bbox_j[2] - bbox_j[0])
    h_j = max(1.0, bbox_j[3] - bbox_j[1])
    cx_j = bbox_j[0] + w_j / 2.0
    cy_j = bbox_j[1] + h_j / 2.0

    page_w = max(1.0, float(page_w))
    page_h = max(1.0, float(page_h))

    norm_i = [bbox_i[0] / page_w, bbox_i[1] / page_h, bbox_i[2] / page_w, bbox_i[3] / page_h]
    norm_j = [bbox_j[0] / page_w, bbox_j[1] / page_h, bbox_j[2] / page_w, bbox_j[3] / page_h]

    delta_x = (cx_j - cx_i) / page_w
    delta_y = (cy_j - cy_i) / page_h
    dist = math.sqrt(delta_x**2 + delta_y**2)
    angle = math.atan2(delta_y, delta_x) / math.pi

    # IoU
    ixmin = max(bbox_i[0], bbox_j[0])
    iymin = max(bbox_i[1], bbox_j[1])
    ixmax = min(bbox_i[2], bbox_j[2])
    iymax = min(bbox_i[3], bbox_j[3])
    iw = max(0.0, ixmax - ixmin)
    ih = max(0.0, iymax - iymin)
    inter = iw * ih
    union = (w_i * h_i) + (w_j * h_j) - inter
    iou = inter / max(1.0, union)

    log_w = math.log(w_i / w_j)
    log_h = math.log(h_i / h_j)

    return {
        "norm_bbox_source": [round(v, 4) for v in norm_i],
        "norm_bbox_target": [round(v, 4) for v in norm_j],
        "delta_x": round(delta_x, 4),
        "delta_y": round(delta_y, 4),
        "distance": round(dist, 4),
        "angle": round(angle, 4),
        "iou": round(iou, 4),
        "log_w_ratio": round(log_w, 4),
        "log_h_ratio": round(log_h, 4),
        "feature_vector": [
            norm_i[0], norm_i[1], norm_i[2], norm_i[3],
            norm_j[0], norm_j[1], norm_j[2], norm_j[3],
            delta_x, delta_y, dist, angle, iou, log_w, log_h
        ]
    }
