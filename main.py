import numpy as np
import cv2
import yaml

# 檔案路徑
video = "videos/white_smoke.mp4"
save_video = "saved_videos/white_smoke.mp4"
yaml_file = "data/white_smoke.yml"


cap = cv2.VideoCapture(video)
width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

points = []
click_count = 0
id = 0
LAPLACIAN = 1.4
DETECT_DELAY = 1
bounds = []
smoke_mask = []
data = []
yaml_data = []
detection_data = []
warning = False

# 選擇是否儲存影片
# 選擇是否使用已儲存的資料
config = {
    "save_video": False,
    "saved_yaml_data": False
}

# 儲存影片
if config["save_video"]:
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        fps_cur = int(cap.get(cv2.CAP_PROP_FPS))
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(save_video, fourcc, fps_cur, size, True)
    except:
        print("[INFO] could not determine in video")

# 讀取已儲存的偵測區域資料
if config["saved_yaml_data"]:
    try:
        with open(yaml_file, "r") as input_data:
            if input_data != None:
                yaml_data = yaml.load(input_data)
                for p in yaml_data:
                    id = p['id'] + 1
                for input_yaml in yaml_data:
                    data.append(input_yaml)

                for p in data:
                    coordinates = np.array(p['coordinates'])
                    rect = cv2.boundingRect(coordinates)
                    new_coordinates = coordinates.copy()
                    new_coordinates[:, 0] = coordinates[:, 0] - rect[0]
                    new_coordinates[:, 1] = coordinates[:, 1] - rect[1]
                    bounds.append(rect)

                    mask = cv2.drawContours(
                        np.zeros((rect[3], rect[2]), dtype=np.uint8),
                        [new_coordinates],
                        contourIdx=-1,
                        color=255,
                        thickness=-1,
                        lineType=cv2.LINE_8)
                    mask = mask == 255
                    smoke_mask.append(mask)
    except:
        pass

statuses = [False] * len(data)
times = [None] * len(data)



# 顯示偵測區域
def draw_contours(frame,
                  coordinates,
                  label,
                  font_color,
                  border_color=(0, 0, 255),
                  line_thickness=1,
                  font=cv2.FONT_HERSHEY_SIMPLEX,
                  font_scale=0.5):
    cv2.drawContours(frame,
                     [coordinates],
                     contourIdx=-1,
                     color=border_color,
                     thickness=2,
                     lineType=cv2.LINE_8)
    moments = cv2.moments(coordinates)

    center = (int(moments["m10"] / moments["m00"]) - 3,
              int(moments["m01"] / moments["m00"]) + 3)

    cv2.putText(frame,
                label,
                center,
                font,
                font_scale,
                font_color,
                line_thickness,
                cv2.LINE_AA)

# 手動畫框
def mouse_callback(event, x, y, flags, params):
    global click_count, id, click, data

    # 點擊滑鼠左鍵畫偵測框
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        click_count += 1

    # 點擊滑鼠右鍵刪除點或線
    if event == cv2.EVENT_RBUTTONDOWN:
        if click_count > 0:
            click_count -= 1
            if points != []:
                points.pop()

    # 點擊滑鼠中鍵刪除偵測框
    if event == cv2.EVENT_MBUTTONDOWN:
        if click_count == 0 and data != []:
            data.pop()
            id -= 1
        if id == 0:
            id = 0


# 取得偵測框的四點座標
def _ROI_points():
    global points, ROI_points
    w = abs(points[0][0] - points[1][0])
    h = abs(points[0][1] - points[1][1])
    x = points[0][0]
    y = points[0][1]
    point_1 = points[0]
    point_3 = points[1]

    if (y < points[1][1]):
        point_2_y = y + h

    if (y > points[1][1]):
        point_2_y = y - h

    if (x < points[1][0]):
        point_4_x = x + w

    if (x > points[1][0]):
        point_4_x = x - w

    point_2 = (points[0][0], point_2_y)
    point_4 = (point_4_x, points[0][1])

    ROI_points = (point_1, point_2, point_3, point_4)

    return ROI_points

# 取得偵測區域資料和辨識遮罩
def handle_done():
    global points, click_count, id, bounds, smoke_mask, statuses, times, ROI_points

    click_count = 0

    _ROI_points()


    detection_data = {'id': id, 'coordinates': [ROI_points[0], ROI_points[1], ROI_points[2], ROI_points[3]]}

    data.append(detection_data)
    points = []

    id += 1

    if bounds != None or smoke_mask != None:
        bounds = []
        smoke_mask = []
        for p in data:
            coordinates = _coordinates(p)

            rect = cv2.boundingRect(coordinates)
            new_coordinates = coordinates.copy()
            new_coordinates[:, 0] = coordinates[:, 0] - rect[0]
            new_coordinates[:, 1] = coordinates[:, 1] - rect[1]
            bounds.append(rect)

            mask = cv2.drawContours(
                np.zeros((rect[3], rect[2]), dtype=np.uint8),
                [new_coordinates],
                contourIdx=-1,
                color=255,
                thickness=-1,
                lineType=cv2.LINE_8)
            mask = mask == 255
            smoke_mask.append(mask)

    statuses = [False] * len(data)
    times = [None] * len(data)



cv2.namedWindow("frame")
cv2.setMouseCallback("frame", mouse_callback)


# 影像處理和黑煙辨識
def apply(index, p):
    global warning, rect
    coordinates = _coordinates(p)

    rect = bounds[index]

    roi = frame[rect[1]:(rect[1] + rect[3]), rect[0]:(rect[0] + rect[2])]
    roi_blurred = cv2.GaussianBlur(roi, (5, 5), 3)
    roi_grayed = cv2.cvtColor(roi_blurred, cv2.COLOR_BGR2GRAY)

    laplacian = cv2.Laplacian(roi_grayed, cv2.CV_64F)

    coordinates[:, 0] = coordinates[:, 0] - rect[0]
    coordinates[:, 1] = coordinates[:, 1] - rect[1]

    status = np.mean(np.abs(laplacian * smoke_mask[index])) < LAPLACIAN

    roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 0, 0])
    upper = np.array([30, 40, 160])
    mask = cv2.inRange(roi_hsv, lower, upper)
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        if cv2.contourArea(contour) > 200:
            warning = True
    return status


def _coordinates(p):
    return np.array(p["coordinates"])

def same_status(coordinates_status, index, status):
    return status == coordinates_status[index]

def status_changed(coordinates_status, index, status):
    return status != coordinates_status[index]


while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 煙霧偵測
    position_in_seconds = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

    for index, c in enumerate(data):
        status = apply(index, c)

        if times[index] is not None and same_status(statuses, index, status):
            times[index] = None
            continue

        if times[index] is not None and status_changed(statuses, index, status):
            if position_in_seconds - times[index] >= DETECT_DELAY:
                statuses[index] = status
                times[index] = None
            continue

        if times[index] is None and status_changed(statuses, index, status):
            times[index] = position_in_seconds

    for index, p in enumerate(data):

        coordinates = _coordinates(p)

        if statuses[index] == True:
            color = (0, 255, 0)

        if statuses[index] == False:
            color = (0, 255, 255)

        if statuses[index] == False and warning == True:
            color = (0, 0, 255)

        draw_contours(frame, coordinates, str(p["id"] + 1), (255, 255, 255), color)

    if click_count == 1:
        cv2.circle(frame, points[0], 2, (255, 0, 0), -2)

    if click_count == 2:
        handle_done()


    cv2.imshow("frame", frame)

    if config["save_video"]:
        writer.write(frame)

    # 按下鍵盤 S 或 s ，直到出現 "Saved successfully" ，即儲存偵測區域資料
    if cv2.waitKey(1) == ord('S') or cv2.waitKey(1) == ord('s'):
        with open(yaml_file, 'w+') as output_data:
            yaml.safe_dump(data, output_data, allow_unicode=None, default_flow_style=None, sort_keys=None)
            print("Saved successfully")

    # 按下鍵盤 Esc，即關閉影片
    if cv2.waitKey(1) == 27:
        break

if config["save_video"]:
    writer.release()

cap.release()
cv2.destroyAllWindows()