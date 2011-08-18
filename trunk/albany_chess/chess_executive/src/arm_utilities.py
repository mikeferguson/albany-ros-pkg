#!/usr/bin/env python

""" 
  Copyright (c) 2011 Michael E. Ferguson.  All right reserved.

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software Foundation,
  Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

import roslib; roslib.load_manifest('chess_executive')
from math import sqrt
import pexpect

import tf
from tf.transformations import euler_from_quaternion, quaternion_from_euler

from chess_msgs.msg import *
from geometry_msgs.msg import Pose, PoseStamped
from simple_arm_server.msg import *
from simple_arm_server.srv import * 

from chess_utilities import SQUARE_SIZE, castling_extras
from tuck_arm import *

TIME_FACTOR = 0.5
GRIPPER_OPEN = 0.05
GRIPPER_CLOSE = 0.0075

class ArmPlanner:
    """ Connection to the arm server. """
    
    def __init__(self, srv=None):
        if srv==None:
            rospy.wait_for_service('simple_arm_server/move')
            self.move = rospy.ServiceProxy('simple_arm_server/move', MoveArm) 
        else:
            self.move = srv
        self.tuck_server = tuck_arm()
        self.success = True
        # setup tf for translating poses
        self.listener = tf.TransformListener()

    def execute(self, move, board, nested=False):
        """ Execute a move. """

        # untuck arm
        self.tuck_server.untuck()
        rospy.sleep(3)

        # get info about move        
        (col_f, rank_f) = board.toPosition(move[0:2])
        (col_t, rank_t) = board.toPosition(move[2:])
        fr = board.getPiece(col_f, rank_f)
        to = board.getPiece(col_t, rank_t)

        req = MoveArmRequest()  
        req.header.frame_id = fr.header.frame_id

        # is this a capture?
        if to != None: 
            off_board = ChessPiece()
            off_board.header.frame_id = fr.header.frame_id
            off_board.pose.position.x = -2 * SQUARE_SIZE
            off_board.pose.position.y = SQUARE_SIZE
            off_board.pose.position.z = fr.pose.position.z
            self.addTransit(req, to.pose, off_board.pose)
        
        to = ChessPiece()
        to.header.frame_id = fr.header.frame_id
        to.pose = self.getPose(col_t, rank_t, board, fr.pose.position.z)

        self.addTransit(req, fr.pose, to.pose)
        
        # execute
        try:
            self.success = self.move(req)
            print self.success
        except rospy.ServiceException, e:
            print "Service did not process request: %s"%str(e)

        if move in castling_extras:
            self.execute(castling_extras[move],board)

        if not nested:
            # tuck arm
            self.tuck_server.tuck()
            rospy.sleep(5.0)
        return to.pose


    def addTransit(self, req, fr, to):
        """ Move a piece from 'fr' to 'to' """

        # hover over piece
        action = ArmAction()
        action.type = ArmAction.MOVE_ARM
        action.goal.position.x = fr.position.x
        action.goal.position.y = fr.position.y
        #action.goal.position.z = fr.position.z + 0.1
        action.goal.position.z = 0.15
        q = quaternion_from_euler(0.0, 1.57, 0.0)
        action.goal.orientation.x = q[0]
        action.goal.orientation.y = q[1]
        action.goal.orientation.z = q[2]
        action.goal.orientation.w = q[3]
        action.move_time = rospy.Duration(TIME_FACTOR*5.0)
        req.goals.append(action)

        # open gripper
        action = ArmAction()
        action.type = ArmAction.MOVE_GRIPPER
        action.command = GRIPPER_OPEN
        action.move_time = rospy.Duration(1.0)
        req.goals.append(action)

        # lower gripper
        action = ArmAction()
        action.type = ArmAction.MOVE_ARM
        action.goal.position.x = fr.position.x
        action.goal.position.y = fr.position.y
        action.goal.position.z = fr.position.z + 0.03
        if action.goal.position.z > 0.05:
            action.goal.position.z = 0.05
        #action.goal.position.z = 0.05 # 0.035
        q = quaternion_from_euler(0.0, 1.57, 0.0)
        action.goal.orientation.x = q[0]
        action.goal.orientation.y = q[1]
        action.goal.orientation.z = q[2]
        action.goal.orientation.w = q[3]
        action.move_time = rospy.Duration(TIME_FACTOR*3.0)
        req.goals.append(action)

        # close gripper
        action = ArmAction()
        action.type = ArmAction.MOVE_GRIPPER
        action.command = GRIPPER_CLOSE
        action.move_time = rospy.Duration(3.0)
        req.goals.append(action)

        # raise gripper
        action = ArmAction()
        action.type = ArmAction.MOVE_ARM
        action.goal.position.x = fr.position.x
        action.goal.position.y = fr.position.y
        #action.goal.position.z = fr.position.z + 0.1
        action.goal.position.z = 0.15
        q = quaternion_from_euler(0.0, 1.57, 0.0)
        action.goal.orientation.x = q[0]
        action.goal.orientation.y = q[1]
        action.goal.orientation.z = q[2]
        action.goal.orientation.w = q[3]
        action.move_time = rospy.Duration(TIME_FACTOR*3.0)
        req.goals.append(action)

        # over over goal
        action = ArmAction()
        action.type = ArmAction.MOVE_ARM
        action.goal.position.x = to.position.x
        action.goal.position.y = to.position.y
        action.goal.position.z = 0.15
        q = quaternion_from_euler(0.0, 1.57, 0.0)
        action.goal.orientation.x = q[0]
        action.goal.orientation.y = q[1]
        action.goal.orientation.z = q[2]
        action.goal.orientation.w = q[3]
        action.move_time = rospy.Duration(TIME_FACTOR*5.0)
        req.goals.append(action)

        # lower gripper
        action = ArmAction()
        action.type = ArmAction.MOVE_ARM
        action.goal.position.x = to.position.x
        action.goal.position.y = to.position.y
        action.goal.position.z = 0.06
        q = quaternion_from_euler(0.0, 1.57, 0.0)
        action.goal.orientation.x = q[0]
        action.goal.orientation.y = q[1]
        action.goal.orientation.z = q[2]
        action.goal.orientation.w = q[3]
        action.move_time = rospy.Duration(TIME_FACTOR*3.0)
        req.goals.append(action)
        
        # open gripper
        action = ArmAction()
        action.type = ArmAction.MOVE_GRIPPER
        action.command = GRIPPER_OPEN
        action.move_time = rospy.Duration(1.0)
        req.goals.append(action)
        
        # raise gripper
        action = ArmAction()
        action.type = ArmAction.MOVE_ARM
        action.goal.position.x = to.position.x
        action.goal.position.y = to.position.y
        action.goal.position.z = 0.15
        q = quaternion_from_euler(0.0, 1.57, 0.0)
        action.goal.orientation.x = q[0]
        action.goal.orientation.y = q[1]
        action.goal.orientation.z = q[2]
        action.goal.orientation.w = q[3]
        action.move_time = rospy.Duration(TIME_FACTOR*3.0)
        req.goals.append(action)

    def getPose(self, col, rank, board, z=0):
        """ Find the reach required to get to a position """
        p = Pose()
        if board.side == board.WHITE:
            p.position.x = (col * SQUARE_SIZE) + SQUARE_SIZE/2
            p.position.y = ((rank-1) * SQUARE_SIZE) + SQUARE_SIZE/2
            p.position.z = z
        else:
            p.position.x = ((7-col) * SQUARE_SIZE) + SQUARE_SIZE/2
            p.position.y = ((8-rank) * SQUARE_SIZE) + SQUARE_SIZE/2
            p.position.z = z
        return p

    def getReach(self, col, rank, board):
        """ Find the reach required to get to a position """
        ps = PoseStamped()
        ps.header.frame_id = "chess_board"
        ps.pose = self.getPose(board.getColIdx(col), int(rank), board)
        pose = self.listener.transformPose("arm_link", ps)
        x = pose.pose.position.x
        y = pose.pose.position.y
        reach = sqrt( (x*x) + (y*y) ) 
        print reach
        return reach

