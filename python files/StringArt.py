import pyb
from pyb import Pin, Timer, ExtInt, repl_uart, UART, delay, SPI
import math
import cotask
import task_share
import machine
from machine import Pin, SoftI2C
from lcd_api import LcdApi
from i2c_lcd import I2cLcd
from MS_Paint_Circles import pin_sequence

def I2C_init(PIN, AF):
    PIN_name = str(PIN[1:])
    PIN = Pin(PIN_name, mode=Pin.AF_PP, af=1)
    return PIN

def clock_init(PIN, AF, tim_num, ch_num):
    PIN_name = str(PIN[1:])
    PIN = Pin(PIN_name, mode=Pin.AF_PP, af=1)
    tim = Timer(tim_num, prescaler=0, period=3)
    clk = tim.channel(ch_num, mode=Timer.PWM, pin=PIN, pulse_width=2)
    return PIN

class TMC4210:

    def __init__ (self, EN_PIN, CS_PIN):
        self.EN_PIN = EN_PIN
        self.CS_PIN = CS_PIN

    def EN_init(self): # Active low
        PIN_name = str(self.EN_PIN[1:])
        self.EN_PIN = Pin(PIN_name, mode=Pin.OUT_PP, value=1)
        self.EN_PIN.low() # Enable TMC2208_1
        return self.EN_PIN

    def CS_init(self): # Active low
        PIN_name = str(self.CS_PIN[1:])
        self.CS_PIN = Pin(PIN_name, mode=Pin.OUT_PP, value=1)
        return self.CS_PIN

    def SPI_SendRecv(self,dataSend):
        dataRecv = bytearray(4)
        self.CS_PIN.low()
        spi.send_recv(dataSend, dataRecv, timeout=5000)
        self.CS_PIN.high()
        return dataRecv

    def byteIndex(self, MSB, LSB):

        dataLength = MSB - LSB + 1                   # calculate the data length
        ByteLength = math.ceil(dataLength/8)         # calculate the byte length

        mod = dataLength%8                           # calculate modulos for later check of how many bytes data has crossed
        if mod == 0:
            mod = 8
        if (LSB%8) > (8-mod):                        # Check how many bytes data has crossed
            ByteLength += 1

        stByte = 3 - math.floor(LSB/8)               # Define start byte index based on MSB first
        endByte = stByte - ByteLength + 1            # Define end byte index based on MSB first
        byteIndex = list(range(stByte,endByte-1,-1)) # store the bytes data has crossed in a list

        return byteIndex


    def setVal(self, RegAddr, RW, MSB, LSB, SetVal):

        # Register[0]: Addr
#         print("RegAddr: " + str(RegAddr))
        Register = bytearray(4)
        Register[0] |= ((RegAddr << 1) | RW)
#         print("Register: " + bin(Register[0])+ " | " + bin(Register[1])+ " | " + bin(Register[2])+ " | " + bin(Register[3]))

        # Whether it's a read or write operation
        if RW == READ:
            print('READ')
            pass

        elif RW == WRITE:
            print('WRITE')
            index = self.byteIndex(MSB,LSB)
            SetVal = SetVal << LSB

            while(len(index)):
                if(index[0]==1):
                    Register[1] |= ((SetVal >> 16) & 0xff)

                elif(index[0]==2):
                    Register[2] |= ((SetVal >> 8) & 0xff)

                elif(index[0]==3):
                    Register[3] |= ((SetVal >> 0) & 0xff)

                index.pop(0)

#         print("Register: " + bin(Register[0])+ " | " + bin(Register[1])+ " | " + bin(Register[2])+ " | " + bin(Register[3]) + "\n")
        dataRecv = self.SPI_SendRecv(Register)
        return dataRecv

    def setPulseRampDiv(self, maxSpeed, maxAccel,f_CLK):
        pulseDiv = math.floor(math.log2(f_CLK*2047/(abs(maxSpeed)*2048*32)))
        rampDiv = math.floor(math.log2(f_CLK*f_CLK*2047/(abs(maxAccel)*2**(pulseDiv+29))))

        PulseRampDiv = [pulseDiv,rampDiv]

        return PulseRampDiv

    def setPmulPdiv(self, maxAccel,PulseRampDiv):
        p = maxAccel/(128*2^(PulseRampDiv[1]-PulseRampDiv[0]))
        p_reduced = p * 0.99

        for pdiv in range(14):
            pmul = p_reduced * 9 * 2 ** pdiv - 128
            if 0 <= pmul <= 127:
                pm = pmul + 128
                pd = pdiv

        PmulPdiv = [pm, pd]

        return PmulPdiv

    def motor_init(self,vmin,vmax):

        # initialize chip select (EN, CS)
        self.EN_init()
        self.CS_init()

        # Read from TYPE VERSION register
        print('typeVer_R')
        typeVer_R = self.setVal(RegisterAddress["TYPE_VER"], READ, 23, 0, -1)

        # Enable Step/Direction by setting en_sd bit 1 in IF_CONFIG register
        print('en_sd_W')
        en_sd_W = self.setVal(RegisterAddress["IF_CONFIG"], WRITE, 5, 5, 1)

        # Set the velocity parameters V_MIN and V_MAX
        print('V_MIN_W')
        V_MIN_W = self.setVal(RegisterAddress["V_MIN"], WRITE, 10, 0, vmin)
        print('V_MAX_W')
        V_MAX_W = self.setVal(RegisterAddress["V_MAX"], WRITE, 10, 0, vmax)

        # Set the clock pre-drivers PULSE_DIV and RAMP_DIV
        PulseDiv_RampDiv = self.setPulseRampDiv(2000, 10, 20e6)
        PRD_value = (PulseDiv_RampDiv[0] << 4 | PulseDiv_RampDiv[1])

        print('PULSE_RAMP_DIV_W')
        PulseDiv_W = self.setVal(RegisterAddress["PULSE_RAMP_DIV"], WRITE, 15, 8, PRD_value)

        print("PulseDiv: " + str(PulseDiv_RampDiv[0]))
        print("RampDiv: " + str(PulseDiv_RampDiv[1]) + "\n")

        # Set the A_MAX  with a valid pair of PMUL and PDIV
        print('A_MAX_W')
        A_MAX_W = self.setVal(RegisterAddress["A_MAX"], WRITE, 10, 0, 10)

        # Set Pmul & Pdiv
        PMUL_PDIV = self.setPmulPdiv(10, PulseDiv_RampDiv)
        PMD_value = (round(PMUL_PDIV[0]) << 8 | PMUL_PDIV[1])
        print('PMUL_PDIV_W')
        PMUL_PDIV_W = self.setVal(RegisterAddress["PMUL_PDIV"], WRITE, 14, 0, PMD_value)
        print("PMUL: " + str(PMUL_PDIV[0]))
        print("PDIV: " + str(PMUL_PDIV[1]))

        # Set Ramp_mode
        RM_W = self.setVal(RegisterAddress["R_M"], WRITE, 1, 0, 0)

        # Choose the reference switch configuration. Set mot1r to 1 for a left and a right reference
        # switch. If this bit is not set and the right switch is not to be used, pull REF_R to GND.
        print('mot1r_W')
        mot1r_W = self.setVal(RegisterAddress["MOT1R"], WRITE, 21, 21, 1)

    def motor_Calib(self):
        # Set the position parameters X_TARGET and X_ACTUAL
        # Calibrating: Before overwriting X_ACTUAL choose velocity_mode or hold_mode
        RM_W = self.setVal(RegisterAddress["R_M"], WRITE, 1, 0, 1)
        print('X_ACTUAL_W')
        X_ACTUAL_R = self.setVal(RegisterAddress["X_ACTUAL"], WRITE, 23, 0, 0)

    def motor_Control(self, usteps):
        # Set back to Ramp_mode
        RM_W = self.setVal(RegisterAddress["R_M"], WRITE, 1, 0, 0)
        print('X_TARGET_W')
        X_TARGET_W = self.setVal(RegisterAddress["X_TARGET"], WRITE, 23, 0, usteps) # nema 17 step/revolution : 1600
                                                                                    # MITSUMI step/revolution : 384

def Start_Button(tim):
    Start_flag.put(True)

button_int = ExtInt(Pin.cpu.C13, ExtInt.IRQ_FALLING, Pin.PULL_NONE, Start_Button)

def Task_StringArt():

    WAIT = 0
    DRILL = 1
    LOOP = 2
    CS = 0



#     global CS

    while True:
        if CS == WAIT:
            lcd.putstr("PUSH THE Button")
            delay(1000)
            lcd.clear()
            if(Start_flag.get()):
                print('CS = WAIT & INIT, NS = DRILL')
                lcd.clear()
                lcd.putstr("WAIT&INIT STATE")
                delay(1000)
                # MOTOR INIT
                Motor_Str = TMC4210('PB0','PC0')
                Motor_Str.motor_init(1800,2000)

                Motor_Rot = TMC4210('PC2','PC3')
                Motor_Rot.motor_init(1800,2000)

                Motor_Drill = TMC4210('PB1','PC1')
                Motor_Drill.motor_init(200,200)
                Start_flag.put(False)

                CS = DRILL

            else:
                print('CS = WAIT & INIT, NS = WAIT & INIT')
                CS = WAIT

        elif CS == DRILL:
            print('CS = DRILL, NS = LOOP')
            lcd.clear()
            lcd.putstr("DRILL STATE")
#             Motor_Str.motor_Calib()
            Motor_Rot.motor_Calib()
            Motor_Drill.motor_Calib()
            p = 0
            for i in range(0):
                Motor_Rot.motor_Control(p)
                p += round(3*1600/pinNum)
                delay(2000)
                Motor_Drill.motor_Control(765)
                delay(6000)
                Motor_Drill.motor_Control(450)
                delay(2000)
            Motor_Drill.motor_Control(0)
            CS = LOOP
#             for i in range(1):
#                 Motor_Rot.motor_Control(p)
#                 p += round(3*1600/pinNum)
#                 delay(2000)
#                 Motor_Drill.motor_Control(700)
#                 delay(10000)
#                 for j in range(705, 770, 5):
#                     Motor_Drill.motor_Control(j)
#                     delay(2000)
#                     Motor_Drill.motor_Control(j-5)
#                     delay(2000)
#                 Motor_Drill.motor_Control(600)
#                 delay(6000)
#             Motor_Drill.motor_Control(0)
#             CS = LOOP

        elif CS == LOOP:
            print('CS = LOOP, NS = WAIT')
            lcd.clear()
            lcd.putstr("LOOP STATE")
            for i in range(len(pin_sequence)):
                Motor_Rot.motor_Control(round((3*1600/pinNum)* pin_sequence[i]) + round(3*1600/(pinNum*1.5)))
                delay(4000)
                Motor_Str.motor_Control(2000)
                delay(4000)
                Motor_Rot.motor_Control(round((3*1600/pinNum)* pin_sequence[i]) - round(3*1600/(pinNum*2)))
                delay(4000)
                Motor_Str.motor_Control(-1500)
                delay(4000)
                while (not Start_flag.get()):
                    print('Press the button')
                Start_flag.put(False)
            CS = WAIT
        else:
            print('OHHHHHHHH NOOOOO')
            pass

        yield (0)

if __name__ == "__main__":

    # constants
    WRITE = 0
    READ = 1
    pinNum = 100

    I2C_ADDR = 0x27
    totalRows = 2
    totalColumns = 16

    # dictionary
    RegisterAddress = {
        "X_TARGET":0,
        "X_ACTUAL":1,
        "V_MIN":2,
        "V_MAX":3,
        "V_TARGET":4,
        "V_ACTUAL":5,
        "A_MAX":6,
        "A_ACTUAL":7,
        "PMUL_PDIV":9,
        "R_M":10,
        "PULSE_RAMP_DIV":12,
        "IF_CONFIG":52,
        "TYPE_VER":57,
        "MOT1R":63,
    }

    # initialize fclk
    PB3 = clock_init('PB3', 1, 2, 2)

    # initialize serial peripheral interface
    spi = SPI(2, SPI.MASTER, 1250000, polarity=1, phase=1)

    # initialize I2C
    SCL = I2C_init('PB8', 4)
    SDA = I2C_init('PB9', 4)
    i2c = machine.SoftI2C(sda=SDA, scl=SCL)
    lcd = I2cLcd(i2c, I2C_ADDR, totalRows, totalColumns)

###########################    TASK INIT STARTS   ##############################
    Start_flag = task_share.Share ('h', thread_protect = False, name = "Start Flag")
#     Init_flag = task_share.Share ('h', thread_protect = False, name = "Init Flag")
#     Drill_flag = task_share.Share ('h', thread_protect = False, name = "Drill Flag")
#     String_flag = task_share.Share ('h', thread_protect = False, name = "String Flag")

    Task_StringArt = cotask.Task (Task_StringArt, name = 'Task_StringArt', priority = 1, period = 400, profile = True, trace = False)

    # Add Task_Comms to the task list
    cotask.task_list.append (Task_StringArt)

    # Set up the task scheduler
    vcp = pyb.USB_VCP ()
    while not vcp.any ():
        cotask.task_list.pri_sched ()

    vcp.read ()

    print ('\n' + str (cotask.task_list))
    print (task_share.show_all ())
    print (Task_Comms.ge