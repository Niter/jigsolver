import pdb
import os
import sys
from itertools import combinations, product
import cv2
import numpy as np
from matplotlib import pyplot as plt
from scipy import optimize
from collections import deque

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

disp_factor = 2
display_size = (417 * disp_factor, 542 * disp_factor)

preprocessed_dir = './data/preprocessed/'

def ada_show(img, name="image"):
    cv2.imshow(name, cv2.resize(img, display_size))
    cv2.waitKey(0)

def save_res(func):
    def func_wrapper(*args, **kwargs):
        res_img = func(*args, **kwargs)
        if 'name' in kwargs:
            name = kwargs['name']
            if name != '': cv2.imwrite(preprocessed_dir + '%s.jpg'%name, res_img.astype('uint8'))
        return res_img
    return func_wrapper
    
def img_to_points(img_input):
    return np.array(np.where(img_input > 0)).T

def find_contour(img_input, name=''):
    color_min, color_max = 100, 255
    # thresh = cv2.inRange(img_input, color_min, color_max)
    ret, thresh = cv2.threshold(img_input, color_min, 255, cv2.THRESH_BINARY)
    #ada_show(thresh)
    contours, hierarchy = cv2.findContours(thresh,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    img_contour = np.zeros(img_input.shape, dtype="uint8")  
    # for cont in contours:
    #     print cv2.contourArea(cont)
    filtered_contours = filter(lambda x: cv2.contourArea(x) > 100.0, contours)
    picked_cnt = filtered_contours[0]
    rect = cv2.minAreaRect(picked_cnt)
    cv2.drawContours(img_contour, filtered_contours, -1, (255, 255, 255), -1)
    # ada_show(img_contour)
    cv2.imwrite(preprocessed_dir + '%s.jpg'%name, img_contour)
    return img_contour

def find_corner(img_input, name):
    blockSize, kSize, k = 15, -1, 0.15
    corner = cv2.cornerHarris(img_input, blockSize, kSize, k);
    #print np.where(corner > 0)
    _, img_corner = cv2.threshold(corner, 0, 255, cv2.THRESH_BINARY)
    #print np.sum(corner > 0)
    cv2.imwrite(preprocessed_dir + '%s.jpg'%name, img_corner)
    return img_corner

@save_res
def find_edge(img_input, name=''):
    img_edge = cv2.Canny(img_input, 100, 200)
    return img_edge

@save_res
def focus(img_input, name=''):
    img_contour = find_contour(img_input)
    cropped     = cropper(img_contour)
    return cropped

@save_res
def edging(img_input, name=''):
    img_contour = find_contour(img_input)
    cropped     = cropper(img_contour)
    edge        = find_edge(cropped)
    return edge

def morop(img_input, op, ksize, name):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, ksize))
    res_img = cv2.morphologyEx(img_input, op, kernel)
    return res_img

def cropper(img_input, name=''):
    coordin = np.where(img_input > 0)
    thickness = 30
    def pick_most(idx):
        return max(0, np.min(coordin[idx]) - thickness), np.max(coordin[idx] + thickness)
    topmost, bottommost = pick_most(0)
    leftmost, rightmost = pick_most(1)
    #print topmost, bottommost, leftmost, rightmost
    res_img = img_input[topmost:bottommost, leftmost:rightmost]
    if name != '': cv2.imwrite(preprocessed_dir + '%s.jpg'%name, res_img)
    return res_img

@save_res
def rectanglize(img_input, name=''):
    img_opened = morop(img_input, cv2.MORPH_OPEN, 35, "opened")
    img_closed = morop(img_opened, cv2.MORPH_CLOSE, 60, "closed")
    img_opened = morop(img_closed, cv2.MORPH_OPEN, 50, "opened")
    return img_opened

def kclustering_coordinate(img_input):
    from sklearn.cluster import KMeans
    X = np.array(np.where(img_input > 0)).T
    # n_cluster is 12 becuase there are 16 significant turning points on a opened and closed piece
    kmeans = KMeans(n_clusters=6, random_state=0).fit(X)
    return map(lambda p: (int(p[0]), int(p[1])), kmeans.cluster_centers_)

@save_res
def connect_to_img(points, shape, name=''):
    res_img = np.zeros(shape, dtype="uint8")  
    cv2.drawContours(res_img, [reorder_counterClockwise(points)], -1, 255, thickness=1)
    return res_img

@save_res
def coordinate_to_img(coordinate, shape, name=''):
    res_img = np.zeros(shape, dtype="uint8")  
    for (y, x) in coordinate:
        res_img[y, x] = 255
    return res_img

def kclustering(img_input, name=''):
    cluster_centers = kclustering_coordinate(img_input)
    return coordinate_to_img(cluster_centers, img_input.shape, name=name)

def PolygonArea(corners):
    n = len(corners) # of corners
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += corners[i][0] * corners[j][1]
        area -= corners[j][0] * corners[i][1]
    area = abs(area) / 2.0
    return area

def counterClockwiseSort(xyz):
    """
    Normalise coordinates into [0, 2pi] space and returns sort index
    This function can be used to sort polygon coordinates "counter-clockwise"
    Only does a 2D sort, so takes the two axes with greatest difference.
    """
    index = np.argsort(np.amax(xyz,axis=0)-np.amin(xyz,axis=0))
    xy = xyz[:,index[0:2]]
    return np.argsort((np.arctan(xy[:,1] - np.mean(xy[:,1]), 
        xy[:,0] - np.mean(xy[:,0])) + 2.0 * np.pi) % 2.0 * np.pi)

def rect_area(points):
    points = np.array(points)
    points = points[counterClockwiseSort(points)]
    return PolygonArea(points)

def clustering_to_ertrame(img_input, name=''):
    # kclustering(img_input, name='kclustering_cropped_opened_corner')
    cluster_coord = kclustering_coordinate(img_input)
    sorted_4pt = sorted(np.array(list(combinations(cluster_coord, 4))), key=rect_area)[::-1]
    #for x in sorted_4pt:
    #    if cv2.contourArea(x) != rect_area(x):
    #        print x, cv2.contourArea(x), rect_area(x)
    #        ada_show(coordinate_to_img(x, img_input.shape))
    largest_points = max(np.array(list(combinations(cluster_coord, 4))), key=rect_area)
    #print largest_points
    return coordinate_to_img(largest_points, img_input.shape, name=name)

def openclose_first(img_input):
    img_contour = find_contour(img_input, "contour")
    img_opened = rectanglize(img_contour)
    opened_corner = find_corner(img_opened, "opened_corner")
    cropped_opened_corner = cropper(opened_corner, 'cropped_opened_corner')
    clustering_to_ertrame(cropped_opened_corner, name='largest_kclustering_cropped_opened_corner')

@save_res
def crop_first(img_input, name=''):
    img_contour = find_contour(img_input)
    cropped = cropper(img_contour, name='crop_first_cropped')
    edge = find_edge(cropped, name='crop_first_edge')
    rectanglized_cropped = rectanglize(cropped, name='rectanglized_cropped')
    cornered = find_corner(rectanglized_cropped, 'crop_first_cornered')
    kclustering(cornered, name='crop_first_kclustering')
    clustering_to_ertrame(cornered, name='crop_first_largest')

def reorder_counterClockwise(points):
    return points[counterClockwiseSort(points)]

class Derivative(object):
    @classmethod
    def generic_derivative(cls, img, x_order, y_order, name=''):
        return NotImplemented

class Sobel_Derivative(Derivative):
    @classmethod
    def derivative_func(cls, img, x_order, y_order):
        return cv2.Sobel(img,cv2.CV_64F, x_order, y_order,ksize=3)

    @classmethod
    @save_res
    def generic_derivative(cls, img, x_order, y_order, name=''):
        return cls.derivative_func(img, x_order, y_order)

class Scharr_Derivative(Derivative):
    @classmethod
    def derivative_func(cls, img, x_order, y_order):
        return cv2.Scharr(img, cv2.CV_64F, x_order, y_order)

    @classmethod
    @save_res
    def generic_derivative(cls, img, x_order, y_order, name=''):
        assert(x_order == 0 or y_order == 0)
        res = img
        if x_order > 0: 
            order = x_order
            reducing_func = lambda r: cls.derivative_func(r, 1, 0)
        if y_order > 0: 
            order = y_order
            reducing_func = lambda r: cls.derivative_func(r, 0, 1)
        for i in range(order):
            res = reducing_func(res)
        return res

class Positive_Kernel_Derivative(Derivative):
    first_derivative_kernel = np.array(
                [[0, -3,  3],
                [0, -10, 10],
                [0, -3,   3]])
    first_derivative_kernel_x = first_derivative_kernel
    first_derivative_kernel_y = first_derivative_kernel.T

    second_derivative_kernel = np.array(
                [[  0, 0,  3, -6,   3],
                [  0, 0, 10, -20, 10],
                [  0, 0,  3, -6,   3]])

    @save_res
    def derivative(cls, img_input, kernel, name=''):
        return cv2.filter2D(img_input, cv2.CV_64F, kernel)

    def generic_derivative(cls, img, x_order, y_order, name=''):
        assert(x_order == 0 or y_order == 0)
        if x_order == 1:
            kernel = cls.first_derivative_kernel_x
            res = cls.derivative(img, kernel, name=name)
        if x_order == 2:
            kernel = cls.second_derivative_kernel
            res = cls.derivative(img, kernel, name=name)
        if y_order == 1:
            kernel = cls.first_derivative_kernel_y.T
            res = cls.derivative(img, kernel, name=name)
        if y_order == 2:
            kernel = cls.second_derivative_kernel.T
            res = cls.derivative(img, kernel, name=name)
        return res

class Custom_Kernel_Derivative(Positive_Kernel_Derivative):
    def set_first_kernel(cls, kernel_):
        cls.first_derivative_kernel = kernel_
        cls.first_derivative_kernel_x = kernel_
        cls.first_derivative_kernel_y = kernel_.T

    def set_first_kernel_x(cls, kernel_):
        cls.first_derivative_kernel_x = kernel_

    def set_first_kernel_y(cls, kernel_):
        cls.first_derivative_kernel_y = kernel_

def find_max_points(img_input):
    v = np.argmax(img_input) 
    return (v / img_input.shape[1], v % img_input.shape[1])

top_right_kernel = np.array(
    [[-10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10, -10],
     [  5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [  5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [ 10,  10,  10,  10,  10,  10,  10,  10,  10,  10,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [  5,   5,   5,   5,   5,   5,   5,   5,   5,  10,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [  5,   5,   5,   5,   5,   5,   5,   5,   5,  10,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10,   5,   5,  10,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10,   5,   5,  10,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10,   5,   5,  10,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10,   5,   5,  10,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10,   5,   5,  10,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10,   5,   5,  10,   5,   5, -10, -10, -10, -10, -10, -10, -10],
     [-10, -10, -10, -10, -10, -10, -10,   5,   5,  10,   5,   5, -10, -10, -10, -10, -10, -10, -10]], 
    dtype='float64')

@save_res
def filter_corner(picked_img , kernel, name=''):
    res_img = cv2.filter2D(picked_img, cv2.CV_64F, kernel)
    res_img[np.where(res_img < 0.)] = 0.
    return res_img

def find_top_right_corner(img_input, name=''):
    half_h, half_w = np.array(img_input.shape) / 2
    picked_img = img_input[:half_h, half_w:] * 0.005
    y, x = find_max_points(filter_corner(picked_img, top_right_kernel, name=name))
    return y, x + half_w

def find_top_right_corner(img_input, name=''):
    half_h, half_w = np.array(img_input.shape) / 2
    picked_img = img_input[:half_h, half_w:] * 0.005
    kernel = top_right_kernel
    y, x = find_max_points(filter_corner(picked_img, kernel, name=name))
    return y, x + half_w

def find_top_left_corner(img_input, name=''):
    half_h, half_w = np.array(img_input.shape) / 2
    picked_img = img_input[:half_h, :half_w] * 0.005
    kernel = top_right_kernel[:, ::-1]
    y, x = find_max_points(filter_corner(picked_img, kernel, name=name))
    return y, x

def find_bottom_left_corner(img_input, name=''):
    half_h, half_w = np.array(img_input.shape) / 2
    picked_img = img_input[half_h:, :half_w] * 0.005
    kernel = top_right_kernel[::-1, ::-1]
    y, x = find_max_points(filter_corner(picked_img, kernel, name=name))
    return y + half_h, x

def find_bottom_right_corner(img_input, name=''):
    half_h, half_w = np.array(img_input.shape) / 2
    picked_img = img_input[half_h:, half_w:] * 0.005
    kernel = top_right_kernel[::-1, :]
    y, x = find_max_points(filter_corner(picked_img, kernel, name=name))
    return y + half_h, x + half_w

@save_res
def find_square_corner(img_input, name=''):
    deriv = Custom_Kernel_Derivative()
    kernel = np.array(
        [[-3, -7, -10, 10, 7, 3],
         [-3, -7, -10, 10, 7, 3],
         [-3, -7, -10, 10, 7, 3],
         [-3, -7, -10, 10, 7, 3],
         [-3, -7, -10, 10, 7, 3]], 
        dtype='float64')
    kernel[0, :] *= 0.2
    kernel[1, :] *= 0.5
    kernel[3, :] *= 0.5
    kernel[4, :] *= 0.2
    deriv.set_first_kernel(kernel)
    xder = deriv.generic_derivative(img_input, 1, 0, name=name+'_derivative_x')
    yder = deriv.generic_derivative(img_input, 0, 1, name=name+'_derivative_y')
    sum_der = np.abs(xder) + np.abs(yder)
    res_img = np.zeros(img_input.shape, dtype='float64')
    res_img[np.where(img_input > 0)] = 1.
    res_img = res_img * sum_der
    res_img = sum_der
    return res_img * 0.01

@save_res
def find_curvature(img_input, name=''):
    points = img_to_points(img_input)
    points = reorder_counterClockwise(points)

@save_res
def signed_curvature(x1, x2, y1, y2, name=''):
    res = np.divide((x1 * y2 - y1 * x2), np.power(x1*x1 + y1*y1, 1.5))
    color = np.zeros(list(res.shape) + [3])
    for (i, j) in product(range(res.shape[0]), range(res.shape[1])):
        if res[i, j] > 0: color[i, j, 1] = res[i, j] * 255 * 255
        if res[i, j] < 0: color[i, j, 0] = res[i, j] * -255 * 255
    return color
    #return np.abs(res)

class Derivative_Curvature(object):
    @classmethod
    def __init__(cls, derivative_type, name=''):
        cls.derivative_type = derivative_type
        cls.name = name

    @classmethod
    def find_curvature(cls, img_input):
        img_contour = find_contour(img_input)
        cropped     = cropper(img_contour)
        edge        = find_edge(cropped, name=cls.name+'_derivative_edge')
        xder        = cls.derivative_type.generic_derivative(edge, 1, 0, name=cls.name+'_derivative_x')
        x2der       = cls.derivative_type.generic_derivative(edge, 2, 0, name=cls.name+'_derivative_x_2nd')
        yder        = cls.derivative_type.generic_derivative(edge, 0, 1, name=cls.name+'_derivative_y')
        y2der       = cls.derivative_type.generic_derivative(edge, 0, 2, name=cls.name+'_derivative_y_2nd')
        signed      = signed_curvature(xder, x2der, yder, y2der, name=cls.name+'_curvature_signed')
        return signed

def find_polygon_points(img_input):
    return cv2.approxPolyDP(img_to_points(img_input), 30, True)

def find_polygon_img(img_input, name=''):
    return connect_to_img(np.squeeze(find_polygon_points(img_input))[:, (1, 0)], 
            img_input.shape, name=name)

class Radius_Curvature(object):
    @classmethod
    def __init__(cls, name=''):
        cls.name = name

    @classmethod
    def find_circle(cls, points):
        x, y = points[0], points[1]

        def calc_R(xc, yc):
            """ calculate the distance of each 2D points from the center (xc, yc) """
            return np.sqrt((x-xc)**2 + (y-yc)**2)

        def f_2(c):
            """ calculate the algebraic distance between the data points and 
                the mean circle centered at c=(xc, yc) 
            """
            Ri = calc_R(*c)
            return Ri - Ri.mean()

        center_estimate = np.mean(x), np.mean(y)
        center_2, ier = optimize.leastsq(f_2, center_estimate)
        xc_2, yc_2 = center_2
        Ri_2       = calc_R(*center_2)
        R_2        = Ri_2.mean()
        residu_2   = sum((Ri_2 - R_2)**2)
        return center_2, R_2

    @classmethod
    @save_res
    def find_curvature(cls, img_input, name=''):
        all_points = img_to_points(img_input)
        kSize = 3
        res_img = np.zeros(img_input.shape)
        tar_x, tar_y = 153, 39
        for y, x in all_points:
            neighbor_block = img_input[max(0, y - kSize):(y + kSize), max(0, x - kSize):(x + kSize)]
            neighbor_points = img_to_points(neighbor_block)
            #pdb.set_trace()
            _, R = cls.find_circle(neighbor_points)
            # if ((x - tar_x)**2 + (y - tar_y)**2) < 20: print x, y, R
            # if R > 100.: print x, y, R
            #print x, y, R
            #res_img[y, x] = R
            res_img[y, x] = 1. / max(R, .0001)
            #res_img[y, x] = 1.
        return res_img * 255.
        #return np.log(res_img) * 255. / np.max(np.log(res_img))

@save_res
def ConvHull(img_input, name=''):
    img_contour = find_contour(img_input)
    cropped     = cropper(img_contour)
    img = np.zeros(list(cropped.shape) + [3])
    img[:, :, 0] = cropped
    ret, thresh = cv2.threshold(cropped, 127, 255,0)
    contours,hierarchy = cv2.findContours(thresh,2,1)
    cnt = contours[0]

    hull = cv2.convexHull(cnt,returnPoints = False)
    defects = cv2.convexityDefects(cnt,hull)

    for i in range(defects.shape[0]):
        s,e,f,d = defects[i,0]
        start = tuple(cnt[s][0])
        end = tuple(cnt[e][0])
        far = tuple(cnt[f][0])
        cv2.line(img,start,end,[0,255,0],2)
        cv2.circle(img,far,5,[0,0,255],-1)

    cv2.imshow('img',img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

dir_x = [0, 1, 1, 1, 0, -1, -1, -1]
dir_y = [-1, -1, 0, 1, 1, 1, 0, -1]
class Point(object):
    def __init__(self, x_, y_):
        self.x = x_
        self.y = y_

    def neighbor(self, idx):
        return Point(self.x + dir_x[idx], self.y + dir_y[idx])

    def __repr__(self):
        return "(x: %s, y: %s)"%(str(self.x), str(self.y))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.x == other.x and self.y == other.y
        return False

@save_res
def BFS(img_input, src, dest, name=''):
    queue = deque([src])
    working_path = np.zeros(img_input.shape)

    def is_avail(p):
        return (img_input[p.y, p.x] > 0 or p == dest or p == src) and working_path[p.y, p.x] == 0

    def mark(p):
        working_path[p.y, p.x] = 255

    while True:
        cur = queue.popleft()
        if not is_avail(cur): continue
        mark(cur)
        if cur == dest: return working_path
        for i in range(len(dir_x)):
            next_p = cur.neighbor(i)
            queue.append(next_p)

@save_res
def edge_by_corner(img_input, point_a, point_b, name=''):
    pA = Point(point_a[1], point_a[0])
    pB = Point(point_b[1], point_b[0])
    working_A_path = BFS(img_input, pA, pB)
    working_B_path = BFS(img_input, pB, pA)
    both_worked = working_A_path * working_B_path
    res_img = np.zeros(img_input.shape)
    for y, x in img_to_points(both_worked):
        res_img[y, x] = 255
    return res_img

def edge_feature(img_input):
    return cv2.HuMoments(cv2.moments(img_input)).flatten()

def match_score(feature_A, feature_B, method=2):
    def mize(h):
        return np.sign(h) * np.log(np.abs(feature_A))
    m_A = mize(feature_A)
    m_B = mize(feature_B)
    if method == 1:
        return np.sum(np.abs(np.reciprocal(m_A) - np.reciprocal(m_B)))
    elif method == 2:
        return np.sum(np.abs(m_A - m_B))
    elif method == 3:
        return np.sum(np.abs(np.divide(m_A - m_B, m_A)))

def shape_matching(img_A, img_B):
    feature_A = edge_feature(img_A)
    feature_B = edge_feature(img_B)
    return match_score(feature_A, feature_B)


@save_res
def raw_to_edge(img_input, name=''):
    pass

# Load images
raw_data_path = './data/raw_data/'
img_path = raw_data_path + 'puzzle26082017_6.jpg'
imgray = cv2.imread(img_path, cv2.CV_LOAD_IMAGE_GRAYSCALE)
rescan_path = raw_data_path + 'puzzle29082017.jpg'
rescan = cv2.imread(rescan_path, cv2.CV_LOAD_IMAGE_GRAYSCALE)
# openclose_first(imgray)
# crop_first(imgray)
# find_polygon_img(edging(imgray), name='polygon')
# find_polygon_img(rectanglize(focus(imgray)), name='rectanglized_polygon')
# ConvHull(imgray)
# connect_to_img(np.array([[1, 1], [18, 18], [1, 18], [18, 1]]), [20, 20], name='square')
# Derivative_Curvature(Positive_Kernel_Derivative(), 'posfirst').find_curvature(imgray)
# Derivative_Curvature(Sobel_Derivative(), 'sobel').find_curvature(imgray)
# Derivative_Curvature(Scharr_Derivative(), 'scharr').find_curvature(imgray)
# Radius_Curvature().find_curvature(edging(imgray, name='edging'), name='radius_curvature')
# find_square_corner(edging(imgray), name='square_corner')
edged            = edging(imgray)
top_right        = find_top_right_corner(edged, name='top_right')
top_left         = find_top_left_corner(edged, name='top_left')
bottom_left      = find_bottom_left_corner(edged, name='bottom_left')
bottom_right     = find_bottom_right_corner(edged, name='bottom_right')
top_left_right   = edge_by_corner(edged, top_left, top_right, name='top_left_right')
bottom_left_right   = edge_by_corner(edged, bottom_left, bottom_right, name='bottom_left_right')
right_top_bottom = edge_by_corner(edged, top_right, bottom_right, name='right_top_bottom')
left_top_bottom = edge_by_corner(edged, top_left, bottom_left, name='left_top_bottom')
# print edge_feature(top_left_right)
# print edge_feature(right_top_bottom)
# print edge_feature(right_top_bottom)
# print edge_feature(left_top_bottom)
edged_rescan          = edging(rescan, name='edged_rescan')
rescan_top_right      = find_top_right_corner(edged_rescan, name='rescan_top_right')
rescan_top_left       = find_top_left_corner(edged_rescan, name='rescan_top_left')
print rescan_top_right, rescan_top_left
rescan_top_left_right = edge_by_corner(edged_rescan, rescan_top_left, rescan_top_right, name='rescan_top_left_right')
print shape_matching(top_left_right, rescan_top_left_right)
# print shape_matching(top_left_right, bottom_left_right)
# print shape_matching(top_left_right, right_top_bottom)
# print shape_matching(top_left_right, left_top_bottom)
# print shape_matching(left_top_bottom, right_top_bottom)
