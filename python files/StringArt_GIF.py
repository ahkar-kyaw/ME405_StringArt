import math
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import imageio
from math_cropped import pin_sequence
from StringArt_Gen import MAX_LINES,N_PINS

r = 10 #radius
j = 1
filenames = []
for i in range(MAX_LINES):

    # plot circle
    plt.axis("equal")
    plt.xlim(-10, 10)
    plt.ylim(-10, 10)
    circle = plt.Circle((0, 0), 10, fill=False)
    plt.gca().add_patch(circle)

    for i in range(j):
        # plot line
        plt.plot([r*math.cos(-(pin_sequence[i]*math.radians(360/N_PINS))),r*math.cos(-(pin_sequence[i+1]*math.radians(360/N_PINS)))],[r*math.sin(-(pin_sequence[i]*math.radians(360/N_PINS))),r*math.sin(-(pin_sequence[i+1]*math.radians(360/N_PINS)))], color='black',linewidth=0.2)
    filename = f'{i}.png'
    filenames.append(filename)
    plt.savefig(filename)
    plt.close()
    j+=1

with imageio.get_writer('mygif.gif',mode='I') as writer:
    for filename in filenames:
        image = imageio.imread(filename)
        writer.append_data(image)