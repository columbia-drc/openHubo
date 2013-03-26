#!/usr/bin/env python
from numpy import pi,array,deprecate
import openravepy as rave
from TransformMatrix import *
from recorder import viewerrecorder
import time
import datetime
import warnings
import sys
import matplotlib.pyplot as plt
import logging
from optparse import OptionParser,Values
import re
import signal

# Interactive script 
if hasattr(sys,'ps1') or sys.flags.interactive:
    print "Loading OpenHubo interactive tools..."
    import startup

""" A collection of useful functions to run openHubo models.
As common functions are developed, they will be added here.
"""
TIMESTEP=0.001

#KLUDGE: hard code the mapping (how often will it change, really?). Include openhubo synonyms here for fast lookup.
hubo_map={'RHY':26,
              'RHR':27,
              'RHP':28,
              'RKN':29,
              'RKP':29,
              'RAP':30,
              'RAR':31,
              'LHY':19,
              'LHR':20,
              'LHP':21,
              'LKN':22,
              'LKP':22,
              'LAP':23,
              'LAR':24,
              'RSP':11,
              'RSR':12,
              'RSY':13,
              'REB':14,
              'REP':14,
              'RWY':15,
              'RWR':16,
              'RWP':17,
              'LSP':4,
              'LSR':5,
              'LSY':6,
              'LEB':7, 
              'LEP':7, 
              'LWY':8,
              'LWR':9, 
              'LWP':10,
              'NKY':1,
              'HNY':1,
              'NK1':2,
              'HNR':2,
              'NK2':3, 
              'HNP':3, 
              'WST':0,
              'HPY':0,
              'TSY':0,
              'RF1':32,
              'RF2':33,
              'RF3':34, 
              'RF4':35,
              'RF5':36,
              'LF1':37,
              'LF2':38, 
              'LF3':39, 
              'LF4':40, 
              'LF5':41}

class Pose:
    """Easy-to-use wrapper for an array of DOF values for a robot. The Pose class
        behaves like a combination of a dictionary and an array. You can look
        up joints by DOF index, openHubo joint name, or Hubo-ach joint name.

        --Examples--
        1. Create a pose from a robot:
            pose=Pose(robot,[ctrl])
        2. Get / Change a joint value in the local pose:
            pose['REP']
            pose['LHP']=pi/4
        3. Update to the latest robot pose:
            pose.update()
        4. Send a pose to the robot's controller:
            pose.send()
    """
    @staticmethod
    def build_jointmap(robot):
        jointmap={}
        for j in robot.GetJoints():
            name=j.GetName()
            index=j.GetDOFIndex()
            jointmap.setdefault(name,index)
            #Add the index itself to replicate old behavior
            # Might be slow, but the point of this is simplicity. 
            #jointmap.setdefault(index,index)

            #Check if hubo-ach name is different and add synonym
            huboname=get_huboname_from_name(name)
            if huboname != name:
                jointmap.setdefault(huboname,index)

        return jointmap

    def __init__(self,robot,ctrl=None):
        self.robot=robot
        self.jointmap=Pose.build_jointmap(robot)
        self.update()
        self.ctrl=ctrl

    def update(self,newvalues=None):
        if newvalues is None:
            self.values=self.robot.GetDOFValues()
        elif len(newvalues)==len(self.values):
            self.values=array(newvalues)
            #TODO: exception throw here?

    def send(self):
        self.ctrl.SetDesired(pose.values)
    
    #TODO: Test if type checking slows down these functions
    def __getitem__(self,key):
        """ Lookup the joint name and return the value"""
        if type(key)==str:
            return self.values[self.jointmap[key]]
        if type(key)==slice or type(key)==int:
            return self.values[key]

    def __setitem__(self,key,value):
        """ Lookup the joint name and assign the specified value """
        if type(key)==str:
            self.values[self.jointmap[key]]=value
        if type(key)==slice or type(key)==int:
            self.values[key]=value

def get_name_from_huboname(inname,robot):
    huboname=inname.encode('ASCII')
    #Cheat a little since hubonames are roman characters
    if (huboname == "LKN" or huboname == "RKN"): 
        name=huboname[0:2]+'P'
    
    elif (huboname == "LEB" or huboname == "REB"): 
        name=huboname[0:2]+'P'
    
    elif (huboname == "WST" ): 
        name = "HPY"
    
    elif (huboname == "NKY"): 
        name="NKY"
    
    elif (huboname == "NK1"): 
        name="HNR"
    
    elif (huboname == "NK2"): 
        name="HNP"
    
    else:
        name=huboname
    #TODO: Fingers

    #FIXME: a bit inefficient but easy to code
    if robot.GetJoint(name):
        return name
    else:
        return None

def get_huboname_from_name(inname):
    name=inname.encode('ASCII')
    #Cheat a little since names are roman characters
    if (name == "LKP" or name == "RKP"): 
        achname=name[0:2]+'N'
    
    elif (name == "LEP" or name == "REP"): 
        achname=name[0:2]+'B'
    
    elif (name == "HPY" or name == "TSY"): 
        achname = "WST"
    
    elif (name == "HNY"): 
        achname="NKY"
    
    elif (name == "HNR"): 
        achname="NK1"
    
    elif (name == "HNP"): 
        achname="NK2"
    
    elif re.search('Knuckle',name) and not re.search('[23]',name):
        name=re.sub('left','LF',name)
        name=re.sub('right','RF',name)
        name=re.sub('Knuckle','',name)
        name=re.sub('Thumb','1',name)
        name=re.sub('Index','2',name)
        name=re.sub('Middle','3',name)
        name=re.sub('Ring','4',name)
        name=re.sub('Pinky','4',name)
        achname = name[:-1]
    else:
        achname=name

    if hubo_map.has_key(achname):
        return achname
    else:
        return None

def build_joint_index_map(robot):
    """ Low level function to build a map of joint names and indices"""
    jointlist=zeros(robot.GetDOF())-1
    for j in robot.GetJoints():
        name=j.GetName()
        print name
        huboname=get_huboname_from_name(name)
        print huboname
        if huboname:
            jointlist[j.GetDOFIndex()]=jointmap[huboname]
    return jointlist

def set_robot_color(robot,dcolor=[.5,.5,.5],acolor=[.5,.5,.5],trans=0,links=[]):
    """Iterate over a robot's links and set color / transparency."""
    if not len(links):
        links=robot.GetLinks()
    for l in links:
        for g in l.GetGeometries():
            g.SetDiffuseColor(dcolor)
            g.SetAmbientColor(acolor)
            g.SetTransparency(trans)

def get_timestamp(lead='_'):
    """Return a simple formatted timestamp for creating files and such."""
    return lead+datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

def pause(t=-1):
    """ A simple pause function to emulate matlab's pause(t). 
    Useful for debugging and program stepping"""
    if t==-1:
        raw_input('Press any key to continue...')
    elif t>=0:
        time.sleep(t)

@deprecate        
def makeNameToIndexConverter(robot,autotranslate=True):
    """ A closure to easily convert from a string joint name to the robot's
    actual DOF index. 
    
    Example usage:
        #create function for a robot
        pose=robot.GetDOFValues()
        ind = make_name_to_index_converter(robot)
        #Use the function to find an index in a vector of DOF values
        pose[ind('LHP')]=pi/4
        #This way you don't have to remember the DOF index of a joint to tweak it.

    NOTE: Deprecated 3/25/2013
    """
    return make_name_to_index_converter(robot,autotranslate)

def make_name_to_index_converter(robot,autotranslate=True):
    """ A closure to easily convert from a string joint name to the robot's
    actual DOF index. 
    
    Example usage:
        #create function for a robot
        pose=robot.GetDOFValues()
        ind = make_name_to_index_converter(robot)
        #Use the function to find an index in a vector of DOF values
        pose[ind('LHP')]=pi/4
        #This way you don't have to remember the DOF index of a joint to tweak it.
    """
    if autotranslate:
        def convert(name):
            j=robot.GetJoint(name)
            if j is not None:
                return j.GetDOFIndex()

            j=robot.GetJoint(get_name_from_huboname(name,robot))
            if j is not None:
                return j.GetDOFIndex()
            
            return None
    else:
        def convert(name):
            j=robot.GetJoint(name)
            if j is not None:
                return j.GetDOFIndex()
            else:
                return None
    return convert

@deprecate
def make_dof_value_map(robot):
    names = [j.GetName() for j in robot.GetJoints()]
    indices = [j.GetDOFIndex() for j in robot.GetJoints()]

    def get_dofs():
        values=robot.GetDOFValues()
        for (i,n) in zip(indices,names):
            pose.setdefault(n,values[i])

    return get_dofs

@deprecate
def load_simplefloor(env):
    """ Load up and configure the simpleFloor environment for hacking with
    physics. Sets some useful defaults.
    """
    return load(env,None,'simpleFloor.env.xml',True)

def load(env,robotfile=None,scenefile=None,stop=True,physics=True,ghost=False,options=Values()):
    """ Load files and configure the simulation environment based on arguments and the options structure.    
    The returned tuple contains:
        :robot: handle to the created robot
        :controller: either trajectorycontroller or idealcontroller depending on physics
        name-to-joint-index converter
        :ref_robot: handle to visiualization "ghost" robot
        :recorder: video recorder python class for quick video dumps
    """
    
    if not (type(robotfile) is list or type(robotfile) is str):
        rave.raveLogWarn("Assuming 2nd argument is options structure...")
        options=robotfile

    if hasattr(options,'recordfile'):
        # Set the robot controller and start the simulation
        recorder=viewerrecorder(env,filename=options.recordfile)
        #Default to "sim-timed video" i.e. plays back much faster
        recorder.videoparams[0:2]=[1024,768]
        recorder.realtime=False
    else:
        recorder=None
    
    if not hasattr(options,'stop'):
        options.stop=stop
    if not hasattr(options,'scenefile'):
        options.scenefile=scenefile
    if not hasattr(options,'robotfile'):
        options.robotfile=robotfile
    if not hasattr(options,'physicsfile'):
        if physics is True:
            options.physicsfile='physics.xml'
        else:
            options.physicsfile=physics
    if not hasattr(options,'ghost'):
        options.ghost=ghost
    if not hasattr(options,'atheight'):
        options.atheight=0.002
    
    #TODO: sort through the spaghetti code... 
    with env:
        if options.stop:
            env.StopSimulation()

        if type(options.scenefile) is list:
            for n in options.scenefile:
                env.Load(n)
        elif type(options.scenefile) is str:
            env.Load(options.scenefile)

        #This method ensures that the URI is preserved in the robot
        if options.robotfile!=None:
            robot=env.ReadRobotURI(options.robotfile)
            env.Add(robot)
        else:
            robot=env.GetRobots()[0]

        robot.SetDOFValues(zeros(robot.GetDOF()))

        ref_robot=None
        if options.physicsfile and env.GetPhysicsEngine().GetXMLId()=='GenericPhysicsEngine':
            rave.raveLogInfo('Loading physics parameters from "{}"'.format(options.physicsfile))
            env.Load(options.physicsfile)
        elif not options.physicsfile:
            env.SetPhysicsEngine(rave.RaveCreatePhysicsEngine(env,'GenericPhysicsEngine'))
        else:
            rave.raveLogWarn("Physics engine already configured, using current settings...")

        #Force new controller since it's easier
        if env.GetPhysicsEngine().GetXMLId()!='GenericPhysicsEngine':
            rave.raveLogInfo('Creating controller for physics simulation')
            controller=rave.RaveCreateController(env,'trajectorycontroller')
            robot.SetController(controller)
            #TODO: validate gains
            controller.SendCommand('set gains 50 0 8')

        else:
            #Just load ideal controller if physics engine is not present
            rave.raveLogInfo('Physics engine not loaded, using idealcontroller...')
            controller=rave.RaveCreateController(env,'idealcontroller')
            robot.SetController(controller)

        if options.ghost:
            #Load ghost robot and colorize
            if options.robotfile:
                ref_robot=load_ghost(env,options.robotfile,prefix="ref_")
                #If using physics, link robots together (assumes that proper controller is used)
                if options.physicsfile:
                    controller.SendCommand("set visrobot "+ref_robot.GetName())

        collisionChecker = rave.RaveCreateCollisionChecker(env,'pqp')
        if collisionChecker==None:
            collisionChecker = rave.RaveCreateCollisionChecker(env,'ode')
            rave.raveLogWarn('Using ODE collision checker since PQP is not available...')
        env.SetCollisionChecker(collisionChecker)
   
    ind=makeNameToIndexConverter(robot)

    if options.atheight:
        align_robot(robot,options.atheight)
        if ref_robot:
            align_robot(ref_robot,options.atheight)

    return (robot,controller,ind,ref_robot,recorder)

def load_ghost(env,robotname,prefix="ref_",color=[.8,.8,.4]):
    """ Create a ghost robot to overlay with an existing robot in the world to show an alternate state."""

    ref_robot=env.ReadRobotURI(robotname)
    ref_robot.SetName(prefix+ref_robot.GetName())
    ref_robot.Enable(False)
    env.Add(ref_robot)
    ref_robot.SetController(rave.RaveCreateController(env,'mimiccontroller'))
    set_robot_color(ref_robot,color,color,trans=.5)
    return ref_robot

def make_ghost_from_robot(robot,prefix="ref_",color=[.8,.8,.4]):
    """ Not yet implemented """
    pass

def align_robot(robot,floorheight=0.002,floornormal=[0,0,1]):
    """ Align robot to floor, spaced slightly above"""
    env=robot.GetEnv()
    vertex1=zeros(3)
    #vertex2=zeros(3)
    with env:
        for l in robot.GetLinks():
            bb=l.ComputeAABB()
            vertex1=minimum(bb.pos()-bb.extents(),vertex1)
            #vertex2=maximum(bb.pos()+bb.extents(),vertex2)
        T=robot.GetTransform()
        dh=floorheight-vertex1[2]

        # add height change to robot
        T[2,3]+=dh
        robot.SetTransform(T)
        #TODO: reset velocity?

@deprecate
def load_rlhuboplus(env,scenename=None,stop=False):
    """ Load the rlhuboplus model into the given environment, configuring a
    servocontroller and a reference robot to show desired movements vs. actual
    pose. The returned tuple contains the robots, controller, and a
    name-to-joint-index converter.
    """
    return load(env,'rlhuboplus.robot.xml',scenename,stop)

def hubo2_left_palm():
    R=mat([[-0.5000,    -0.5000,   0.7071],
        [0.5000,   0.5000,   0.7071],
        [-0.7071,   0.7071,         0]])

    t=mat([.009396,-.010145,-.022417]).T
    return MakeTransform(R,t)

def hubo2_right_palm():
    return MakeTransform(R_hubo2_right_palm(),t_hubo2_right_palm())

def R_hubo2_right_palm():
    return mat( [[-0.5000,    0.5000,    0.7071],
            [-0.5000,    0.5000,   -0.7071],
            [-0.7071,   -0.7071,         0]])

def t_hubo2_right_palm():
    return mat([.009396,.010145,-.022417]).T

def hubo2_left_foot():
    R=mat(eye(3))
    t=mat([-.040497,.005,-.104983]).T+mat([0.042765281437, -0.002531569047,0.063737248723]).T
    return MakeTransform(R,t)

def hubo2_right_foot():
    R=mat(eye(3))
    t=mat([-.040497,-.005,-.104983]).T+mat([0.042765281437, 0.002531569047,0.063737248723]).T
    return MakeTransform(R,t)

############################################################
# Mass functions

def find_com(robot):
    com_trans=array([0.0,0.0,0.0])
    mass=0.0
    for l in robot.GetLinks():
        com_trans+= (l.GetGlobalCOM()*l.GetMass())
        mass+=l.GetMass()

    com=com_trans/mass
    return com

def find_mass(robot):
    mass=0
    for l in robot.GetLinks():
        mass=mass+l.GetMass()

    return mass

@deprecate
def plotProjectedCOG(robot):
    return plot_projected_com(robot)

@deprecate
def plotBodyCOM(env,link,handle=None,color=array([0,1,0])):
    return plot_body_com(link,handle,color)

def plot_body_com(link,handle=None,color=array([0,1,0])):
    """ efficiently plot the center of mass of a given link"""
    origin=link.GetGlobalCOM()
    m=link.GetMass()
    #Fetch environment from robot parent
    env=link.GetParent().GetEnv()
    if handle==None:
        handle=env.plot3(points=origin,pointsize=5.0*m,colors=color)
    else:
        neworigin=[1,0,0,0]
        neworigin.extend(origin.tolist())
        handle.SetTransform(matrixFromPose(neworigin))
    return handle

def plot_projected_com(robot):
    proj_com=find_com(robot)
    #assume zero height floor for now
    proj_com[-1]=0.001

    env=robot.GetEnv()
    handle=env.plot3(points=proj_com,pointsize=12,colors=array([0,1,1]))
    return handle

def plot_masses(robot,color=array([.8,.5,.3]),ccolor=[0,.8,.8]):
    handles=[]
    total=0
    for l in robot.GetLinks():
        origin=l.GetGlobalCOM()
        m=l.GetMass()
        total+=m
        #Area of box corresponds to mass
        handles.append(robot.GetEnv().plot3(origin,m/100.,array(color),True))
    handles.append(robot.GetEnv().plot3(find_com(robot),m/100.,ccolor,True))
    return handles

def CloseLeftHand(robot,angle=pi/2):
    #assumes the robot is still, uses direct control
    #TODO: make this general, for now only works on rlhuboplus
    #TODO: use trajectory controller to close hands smoothly
    ctrl=robot.GetController()
    ctrl.SendCommand('set radians')
    fingers=['Index','Middle','Ring','Pinky','Thumb']

    prox=[robot.GetJoint('left{}Knuckle{}'.format(x,1)).GetDOFIndex() for x in fingers]
    med=[robot.GetJoint('left{}Knuckle{}'.format(x,2)).GetDOFIndex() for x in fingers]
    dist=[robot.GetJoint('left{}Knuckle{}'.format(x,3)).GetDOFIndex() for x in fingers]
    pose=robot.GetDOFValues()
    for k in prox:
        pose[k]=angle
    ctrl.SetDesired(pose)
    time.sleep(1)

    for k in med:
        pose[k]=angle
    ctrl.SetDesired(pose)
    time.sleep(1)

    for k in dist:
        pose[k]=angle
    ctrl.SetDesired(pose)
    time.sleep(1)

def CloseRightHand(robot,angle=pi/2):
    #assumes the robot is still, uses direct control
    #TODO: make this general, for now only works on rlhuboplus
    
    ctrl=robot.GetController()
    ctrl.SendCommand('set radians')
    fingers=['Index','Middle','Ring','Pinky','Thumb']

    prox=[robot.GetJoint('right{}Knuckle{}'.format(x,1)).GetDOFIndex() for x in fingers]
    med=[robot.GetJoint('right{}Knuckle{}'.format(x,2)).GetDOFIndex() for x in fingers]
    dist=[robot.GetJoint('right{}Knuckle{}'.format(x,3)).GetDOFIndex() for x in fingers]

    #TODO: Fix this "cheat" of waiting a fixed amount of real time
    pose=robot.GetDOFValues()
    for k in prox:
        pose[k]=angle
    ctrl.SetDesired(pose)
    time.sleep(1)

    for k in med:
        pose[k]=angle
    ctrl.SetDesired(pose)
    time.sleep(1)

    for k in dist:
        pose[k]=angle
    ctrl.SetDesired(pose)
    time.sleep(1)
    return True

class ServoPlotter:
    """A simple class to import recorded servo data and plot a specific subset
    of joints. matplotlib.pyplot commands are embedded in the class so you can
    easily customize the plot.
    :param filename: file containing recorded servo data. """

    def __init__(self,filename=None,servolist=[]):
        self.jointdata={}
        self.import_servo_data(filename)
        self.plt=plt
        self.show=plt.show
        if len(servolist)>0:
            self.plot(servolist)

    def import_servo_data(self,filename,clearold=False):
        """ Read in servo data from the filename provided."""

        with open(filename,'r') as f:
            gainstring=f.readline().rstrip()
            servostrings=f.readlines()

        if clearold:
            self.jointdata={}

        for l in servostrings:
            data=l.rstrip().split(' ')
            #Store a dictionary of lists?
            self.jointdata.setdefault(data[0],[float(x) for x in data[1:]])

    def plot(self,servolist=[]):
        for s in servolist:
            REF='{}_REF'.format(s)
            plt.plot(self.jointdata[REF],'+',hold=True)
            plt.plot(self.jointdata[s],hold=True)


#-----------------------------------------------------------
# Executable setup
#-----------------------------------------------------------
from openravepy.misc import OpenRAVEGlobalArguments
import atexit

def safe_quit(env):
    """ Exit callback to ensure that openrave closes safely."""
    #Somewhat overkill, try to avoid annoying segfaults
    rave.raveLogDebug("Safely exiting rave environment...")
    if env:
        env.Destroy()
    rave.RaveDestroy()

parser = OptionParser(description='OpenHubo: perform experiments with virtual hubo modules.',
                      usage='usage: %prog [options] script')
OpenRAVEGlobalArguments.addOptions(parser)
parser.add_option('--robot', action="store",type='string',dest='robotfile',default='rlhuboplus.robot.xml',
                  help='Robot XML file to load (default=%default)')
parser.add_option('--scene', action="store",type='string',dest='scenefile',default='floor.env.xml',
                  help='Scene file to load (default=%default)')
parser.add_option('--example', action="store",type='string',dest='example',default=None,
                  help='Run an example')
parser.add_option('--nointeract', action="store_false",dest='interact',default=True,
                  help='Disable interactive prompt and exit after running')
parser.add_option('--debug', action="store_true",dest='pydebug',default=False,
                  help='Enable python debugger')
parser.add_option('--record', action="store",dest='recordfile',default=None,
                  help='Enable video recording to the given file name (requires script commands to start and stop)')
parser.add_option('--physicsfile', action="store",dest='physicsfile',default=None,
                  help='Load physics engine config from XML file')
parser.add_option('--ghost', action="store_true",dest='ghost',default=None,
                  help='Create a ghost robot to show desired vs. actual pose')
parser.add_option('--atheight', action="store",type="float", dest='atheight',default=None,
                  help='Align the robot\'s feet at the given absolute Z height')

def show_options():
    parser.print_help()

def setup(viewername=None,create=True):
    """ Setup openhubo environment and viewer when run from the command line.
    :param viewername: Name of viewer plugin to use (defaults to no viewer)
    :param create: If true, set up and return environment. Otherwise, parse and return options.
    """
    (options, leftargs) = parser.parse_args()

    if viewername:
        #Overwrite command line option with explicit argument?
        options._viewer=viewername
    if options.robotfile=="none" or options.robotfile=="None":
        #use command line fake for "none"
        options.robotfile=None

    if create:
        env=rave.Environment()
        atexit.register(safe_quit,env)
        OpenRAVEGlobalArguments.parseEnvironment(options,env)
        return (env,options)
    elif len(leftargs)>0:
        return (options,leftargs[0])
    else:
        return (options,None)



if __name__ == '__main__':
    """Run openhubo to see example files and use the IPython shell for inspection and debugging."""
    def signal_handler(signal, frame):
        try:
            import IPython
            IPython.embed() 
        except ImportError:
            print "IPython not installed!"
    signal.signal(signal.SIGINT, signal_handler)
    (options,scriptname)=setup(None,False)

    if options.pydebug:
        import debug

    if options.example or scriptname:

        if scriptname:
            execfile(scriptname)
        else:
            import fnmatch
            import os
            from openravepy import raveLogInfo
            expath=os.environ['OPENHUBO_DIR'] + '/examples/'
            for f in os.listdir(expath):
                if fnmatch.fnmatch(f, options.example):
                    raveLogInfo("Found example {}".format(options.example))
                    break
            execfile(expath+options.example)
    else:
        #Enable interactive mode and load a simple environment
        options.interact=True
        execfile('interactive_sandbox.py')
        
            
    if options.interact:
        try:
            import IPython
            IPython.embed() 
            print "Cleaning up after inspection..."
        except ImportError:
            print "IPython not installed!"
