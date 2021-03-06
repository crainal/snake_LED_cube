import sys
import random
import time
import threading
import multiprocessing
from multiprocessing.sharedctypes import Value, Array
import copy
from collections import namedtuple

from grove import imu9250

from led_matrix import *

from utils import LEDCubeMap

TIME_STEP_LENGTH = 0.3


class Snake:
    def __init__(self, cube_map, cube_motion=None):
        self.cube_map = cube_map
        self.cube_motion = cube_motion

        self.side_up = 'n'

        self.x = []
        self.y = []
        self.step = 1
        self.length = 3
        self.control = 0
        self.score = 0
        self.dead = False

        self.num_food = 5
        self.found_food = False
        self.food = []
        for _ in range(self.num_food):
            self.new_food_pos()

        # Starting points
        self.x = [32, 31, 31]
        self.y = [32, 32, 32]
        self.s_len = 3
        self.x_pos = 32
        self.y_pos = 32

        self.face = "t"
        self.direction = "e"
        self.directions = ['u', 'd', 'n', 'e', 's', 'w']
        self.opposite = {'t': 'b', 'b': 't', 'n':'s', 'e':'w', 's':'n', 'w':'e'}
        self.updateCount = 0
        self.updateCountMax = 0

        # Break down and documentation of of my cube orientation
        # Top NE(0,0) NW(0,63) SW(63, 63) SE(63, 0)
        # North TE(192,63) TW(192,0) BE(255,63) BW(255,0)
        # East ST(128,63) NT(128,0) BS(191,63) BN(191,0)
        # South TW(64,63) TE(64,0) BE(127,0) BW(127,63)
        # West TN(256,63) TS(256,0) BN(319,63) BS(319,0)
        # Bottom NW(320,63) NE(383,63) SW(320,0) SE(383,0)

        self.change_direction_map = {
            'tnr': 'e',
            'tnl': 'w',
            'tsr': 'w',
            'tsl': 'e',
            'ter': 's',
            'tel': 'n',
            'twr': 'n',
            'twl': 's',

            'bnr': 'w',
            'bnl': 'e',
            'bsr': 'e',
            'bsl': 'w',
            'ber': 'n',
            'bel': 's',
            'bwr': 's',
            'bwl': 'n',

            'ner': 't',
            'nel': 'b',
            'nwr': 'b',
            'nwl': 't',
            'ntr': 'w',
            'ntl': 'e',
            'nbr': 'e',
            'nbl': 'w',

            'ser': 'b',
            'sel': 't',
            'swr': 't',
            'swl': 'b',
            'str': 'e',
            'stl': 'w',
            'sbr': 'w',
            'sbl': 'e',

            'etr': 'n',
            'etl': 's',
            'ebr': 's',
            'ebl': 'n',
            'enr': 'b',
            'enl': 't',
            'esr': 't',
            'esl': 'b',

            'wtr': 's',
            'wtl': 'n',
            'wbr': 'n',
            'wbl': 's',
            'wnr': 't',
            'wnl': 'b',
            'wsr': 'b',
            'wsl': 't',

        }
        self.transition_map = {}
        # keys are [single char for face][single char for direction][x coord][y coord]:(x,y)
        for i in range(64):
            # Top North
            self.transition_map[f"tn0.{i}"] = (192, 63 - i, 'nb')
            self.transition_map[f"nt192.{63 - i}"] = (0, i, 'ts')
            # Top West
            self.transition_map[f"tw{i}.63"] = (256, 63 - i, 'wb')
            self.transition_map[f"wt256.{63 - i}"] = (i, 63, 'te')
            # Top East
            self.transition_map[f"te{i}.0"] = (128, i, 'eb')
            self.transition_map[f"et128.{i}"] = (i, 0, 'tw')
            # Top South
            self.transition_map[f"ts63.{i}"] = (64, i, 'sb')
            self.transition_map[f"st64.{i}"] = (63, i, 'tn')
            # North East
            self.transition_map[f"ne{i+192}.63"] = (128 + i, 0, 'es')
            self.transition_map[f"en{128 + i}.0"] = (i+192, 63, 'nw')
            # North West
            self.transition_map[f"nw{i+192}.0"] = (256 + i, 63, 'ws')
            self.transition_map[f"wn{256 + i}.63"] = (i+192, 0, 'ne')
            # South West
            self.transition_map[f"sw{i+64}.63"] = (256 + i, 0, 'wn')
            self.transition_map[f"ws{256 + i}.0"] = (i+64, 63, 'se')
            # South East
            self.transition_map[f"se{i+64}.0"] = (i+128, 63, 'en')
            self.transition_map[f"es{i+128}.63"] = (i+64, 0, 'sw')
            # Bottom North
            self.transition_map[f"bn{i+320}.63"] = (255, i, 'nt')
            self.transition_map[f"nb255.{i}"] = (i+320, 63, 'bs')
            # Bottom East
            self.transition_map[f"be383.{i}"] = (191, 63 - i, 'et')
            self.transition_map[f"eb191.{63 - i}"] = (383, i, 'bw')
            # Bottom West
            self.transition_map[f"bw320.{i}"] = (319, i, 'wt')
            self.transition_map[f"wb319.{i}"] = (320, i, 'be')
            # Bottom South
            self.transition_map[f"bs{320+i}.0"] = (127, 63 - i, 'st')
            self.transition_map[f"sb127.{63 - i}"] = (320+i, 0, 'bn')

        self.coord_map = {
                            "tn": "xd",
                            "nt": "xd",
                            "tw": "yu",
                            "wt": "xd",
                            "te": "yd",
                            "et": "xd",
                            "ts": "xu",
                            "st": "xd",
                            "ne": "yu",
                            "en": "yd",
                            "nw": "yd",
                            "wn": "yu",
                            "sw": "yu",
                            "ws": "yd",
                            "se": "yd",
                            "es": "yu",
                            "bn": "yu",
                            "nb": "xu",
                            "be": "xu",
                            "eb": "xu",
                            "bw": "xd",
                            "wb": "xu",
                            "bs": "yd",
                            "sb": "xu"
                          }

    def new_food_pos(self):
        good_food = False
        food = namedtuple("Food", "x y")
        while not good_food:
            food.x = random.randint(0, 383)  # (0, 319) to exclude bottom, (0, 383) to include bottom
            food.y = random.randint(0, 63)
            good_food = True
            for x, y in zip(self.x, self.y):
                if food.y == y and food.x == x:
                    good_food = False
                    continue
            for existing_food in self.food:
                if existing_food.x == food.x and existing_food.y == food.y:
                    good_food = False
                    continue
        self.food.append(food)
        self.cube_map.set_map_point(food.x, food.y, color=(0, 255, 0))
        # self.cube_map.set_map_point(self.food_x + 1, self.food_y + 1, color=(0, 255, 0))
        # self.cube_map.set_map_point(self.food_x, self.food_y + 1, color=(0, 255, 0))
        # self.cube_map.set_map_point(self.food_x + 1, self.food_y, color=(0, 255, 0))

    def update(self):
        self.updateCount += 1
        if self.updateCount > self.updateCountMax:
            self.side_up = self.cube_motion.get_face()
            if self.side_up != self.face and self.opposite[self.side_up] != self.direction:
                self.direction = self.side_up
            # print(f"On face {self.face} going {self.direction}")
            # Uncomment this to make the game stop every cycle without input
            # elif pad_direction == "up":
            #     pass
            # else:
            #     return

            new_face = False
            try:
                position_key = f"{self.face}{self.direction}{self.x_pos}.{self.y_pos}"
                new_x, new_y, face_change = self.transition_map[position_key]
                self.x_pos = new_x
                self.x.append(new_x)
                self.y_pos = new_y
                self.y.append(new_y)
                self.face = face_change[0]
                self.direction = face_change[1]
                # print(f"On face {self.face} going {self.direction}")
                new_face = True
            except KeyError:
                pass
            if not new_face:
                try:
                    direction = self.coord_map[self.face + self.direction]
                    if direction == "yu":
                        self.y_pos += self.step
                        self.y.append(self.y_pos)
                        self.x.append(self.x_pos)
                    elif direction == "yd":
                        self.y_pos -= self.step
                        self.y.append(self.y_pos)
                        self.x.append(self.x_pos)
                    elif direction == "xu":
                        self.x_pos += self.step
                        self.x.append(self.x_pos)
                        self.y.append(self.y_pos)
                    elif direction == "xd":
                        self.x_pos -= self.step
                        self.x.append(self.x_pos)
                        self.y.append(self.y_pos)
                    else:
                        raise TypeError
                except KeyError:
                    # ToDo: Investigate if I should pass here or if this is bad
                    pass
                xy = [[x, y] for x, y in zip(self.x, self.y)]
                if xy.count(xy[-1]) > 1:
                    self.dead = True

            # print(f"On face {self.face} going {self.direction}")
            # print(f"X: {self.x_pos} Y: {self.y_pos}")
            for food in self.food:
                if self.x_pos == food.x and self.y_pos == food.y:
                    # Food found!!!
                    self.cube_map.set_map_point(self.x_pos, self.y_pos)
                    self.new_food_pos()
                    self.s_len += 30
                    self.score += 1
                    self.found_food = True
                    print(f"Found food! Score: {self.score}")
                    break
                else:
                    self.found_food = False
            if not self.found_food:
                # update previous positions
                if len(self.x) > self.s_len:
                    self.cube_map.unset_map_point(self.x[0], self.y[0])
                    self.x.pop(0)
                    self.y.pop(0)
                self.cube_map.set_map_point(self.x_pos, self.y_pos)

            self.updateCount = 0


def play_snake(matrix, cube_motion):
    image = Image.new("RGB", (6 * 64, 64))
    pixels = image.load()
    cube_map = LEDCubeMap(rows=image.size[0], cols=image.size[1], pixel_input_map=pixels)

    snake = Snake(cube_map, cube_motion=cube_motion)

    last_time = time.process_time()
    while True:
        new_time = time.process_time()
        if new_time - last_time > TIME_STEP_LENGTH:
            last_time = time.process_time()
            snake.update()
            matrix.Clear()
            matrix.SetImage(image)
            if snake.dead:
                return snake.score


class CubeMotion:
    def __init__(self, imu):
        self.imu = imu
        self.rotating = Value('i', 0)
        self.rotational_axis = Array('c', '')
        self.last_rotational_axis = None
        self.rotational_distance = 0.0
        self.face_up = Array('c', b't')
        self.exit = False

    def update(self):
        accl = self.imu.readAccel()
        gyro = self.imu.readGyro()
        gx, gy, gz = gyro.values()
        ax, ay, az = accl.values()
        if gx < 20 and gy < 20 and gz < 20:
            if az > 0.6:
                self.face_up.value = b't'
            elif az < -0.6:
                self.face_up.value = b'b'
            elif ax > 0.3 and ay > 0.3:
                self.face_up.value = b'e'
            elif ax < -0.3 and ay < -0.3:
                self.face_up.value = b'w'
            elif ax < -0.3 and ay > 0.3:
                self.face_up.value = b'n'
            elif ax > 0.3 and ay < -0.3:
                self.face_up.value = b's'

        if gz > 15:
            self.rotation = True
            self.rotational_axis = "z+"
        elif gz < -15:
            self.rotation = True
            self.rotational_axis = "z-"
        elif gx > 15 and gy > 15:
            self.rotating = 1
            self.rotational_axis = "x+"
        elif gx < -15 and gy < -15:
            self.rotating = 1
            self.rotational_axis = "x-"
        elif gx < -15 and gy > 15:
            self.rotating = 1
            self.rotational_axis = "y+"
        elif gx > 15 and gy < -15:
            self.rotating = 1
            self.rotational_axis = "y-"
        else:
            self.rotating = 0
            self.last_rotational_axis = self.rotational_axis
            self.rotational_distance = 0.0

    def track_motion(self):
        while not self.exit:
            self.update()

    def get_face(self):
        return self.face_up.value.decode('utf-8')


class CubeMenu:
    def __init__(self, matrix, cube_motion):
        self.matrix = matrix
        self.cube_motion = cube_motion
        self.image = None
        self.menu_exit = False
        self.move = ""
        self.menu_position = 0
        self.menu_updated = time.time()
        self.menu = {0: "snake", 1: "exit"}
        self.cursor_position = {0: (1, 5, 2, 6), 1: (1, 20, 2, 21)}
        self.menu_items = len(self.menu)
        self.sem = threading.Semaphore(1)

    def display_menu(self):
        while True:
            time.sleep(0.5)
            with self.sem:
                self.matrix.SetImage(self.image, 0, 0)
            if self.menu_exit:
                return

    def update_menu(self, image):
        new_image = copy.copy(image)
        draw = ImageDraw.Draw(new_image)
        time_now = time.time()
        if time_now - self.menu_updated > 0.5:
            tilt = self.cube_motion.get_face()
            if tilt == "e":
                self.menu_updated = time.time()
                self.menu_position += 1
                if self.menu_position >= self.menu_items:
                    self.menu_position = self.menu_items - 1
            elif tilt == "w":
                self.menu_updated = time.time()
                self.menu_position -= 1
                if self.menu_position < 0:
                    self.menu_position = 0
            elif tilt == "s":
                # We have a selection!
                return self.menu[self.menu_position]

        if self.menu_position == 0:
            draw.rectangle(self.cursor_position[self.menu_position], fill=(0, 0, 0), outline=(255, 255, 255))
        elif self.menu_position == 1:
            draw.rectangle(self.cursor_position[self.menu_position], fill=(0, 0, 0), outline=(255, 255, 255))

        return new_image

    def play_menu(self):
        image1 = Image.new("RGB", (6 * 64, 64))
        self.menu_exit = False

        draw1 = ImageDraw.Draw(image1)
        draw1.rectangle((0, 0, 63, 63), fill=(0, 0, 0), outline=(0, 0, 255))
        draw1.text((3, 0), "Play Snake\nExit", fill=(0, 0, 255))

        image2 = copy.copy(image1)
        draw2 = ImageDraw.Draw(image2)
        draw2.rectangle((1, 5, 2, 6), fill=(0, 0, 0), outline=(255, 255, 255))
        self.image = image1
        display_thread = threading.Thread(target=self.display_menu)
        display_thread.start()
        start_time = time.time()
        while True:
            time.sleep(0.5)
            with self.sem:
                self.image = image1
            time.sleep(0.5)
            update = self.update_menu(image1)
            if type(update) is str:
                break
            with self.sem:
                self.image = update
            if time.time() - start_time > 120:
                break
        self.menu_exit = True
        display_thread.join()
        draw1.rectangle(self.cursor_position[self.menu_position], fill=(0, 0, 0), outline=(20, 255, 255))
        self.matrix.SetImage(image1, 0, 0)
        time.sleep(1)
        self.matrix.Clear()

        return self.menu[self.menu_position]


def main():
    # ToDo: Setup temperature tracking

    imu = imu9250.MPU9250()
    if imu.checkDataReady():
        print("IMU Ready")
    else:
        print("IMU Not Ready!")
        sys.exit()

    cube_motion = CubeMotion(imu)

    matrix = RGBMatrix(options=options)

    cube_menu = CubeMenu(matrix, cube_motion)
    motion_tracking = multiprocessing.Process(target=cube_motion.track_motion)
    motion_tracking.start()

    while True:
        choice = cube_menu.play_menu()
        if choice == "snake":
            score = play_snake(matrix, cube_motion)
            image = Image.new("RGB", (6 * 64, 64))
            draw = ImageDraw.Draw(image)
            for idx in range(8, 383, 64):
                draw.multiline_text((idx, 25), f"Score: {score}", fill=(255, 0, 0))
            for _ in range(10):
                matrix.SetImage(image, 0, 0)
                time.sleep(0.6)
                matrix.Clear()
                time.sleep(0.2)
        elif choice == "exit":
            break

    time.sleep(1)
    matrix.Clear()
    image = Image.new("RGB", (6 * 64, 64))
    draw = ImageDraw.Draw(image)
    draw.multiline_text((1, 1), "Exiting!!!", fill=(255, 0, 0))
    matrix.SetImage(image, 0, 0)
    time.sleep(2)
    matrix.Clear()
    cube_motion.exit = True
    motion_tracking.join()


if __name__ == "__main__":
    main()
