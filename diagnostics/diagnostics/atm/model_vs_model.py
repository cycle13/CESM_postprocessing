from __future__ import print_function

import sys

if sys.hexversion < 0x02070000:
    print(70 * "*")
    print("ERROR: {0} requires python >= 2.7.x. ".format(sys.argv[0]))
    print("It appears that you are running python {0}".format(
        ".".join(str(x) for x in sys.version_info[0:3])))
    print(70 * "*")
    sys.exit(1)

# import core python modules
import errno
import glob
import itertools
import os
import re
import shutil
import traceback

# import the helper utility module
from cesm_utils import cesmEnvLib
from diag_utils import diagUtilsLib
import create_html

# import the MPI related modules
from asaptools import partition, simplecomm, vprinter, timekeeper

# import the diag baseclass module
from atm_diags_bc import AtmosphereDiagnostic

# import the plot classes
from diagnostics.atm.Plots import atm_diags_plot_bc
from diagnostics.atm.Plots import atm_diags_plot_factory

class modelVsModel(AtmosphereDiagnostic):
    """model vs. model atmosphere diagnostics setup
    """
    def __init__(self):
        """ initialize
        """
        super(modelVsModel, self).__init__()

        self._name = 'MODEL_VS_MODEL'
        self._title = 'Model vs. Model'

    def check_prerequisites(self, env, scomm):
        """ check prerequisites
        """
        print("  Checking prerequisites for : {0}".format(self.__class__.__name__))
        super(modelVsModel, self).check_prerequisites(env, scomm)

        # clean out the old working plot files from the workdir
        #if env['CLEANUP_FILES'] in ['T',True]:
        #    cesmEnvLib.purge(env['test_path_diag'], '.*\.gif')
        #    cesmEnvLib.purge(env['test_path_diag'], '.*\.ps')
        #    cesmEnvLib.purge(env['test_path_diag'], '.*\.png')
        #    cesmEnvLib.purge(env['test_path_diag'], '.*\.html')
            

        # create the plot.dat file in the workdir used by all NCL plotting routines
        #diagUtilsLib.create_plot_dat(env['WORKDIR'], env['XYRANGE'], env['DEPTHS'])

        # Set some new env variables
        env['DIAG_CODE'] = env['NCLPATH']
        env['WKDIR'] = env['test_path_diag']
        env['WORKDIR'] = env['test_path_diag']
        if scomm.is_manager():
            if not os.path.exists(env['WKDIR']):
                os.makedirs(env['WKDIR'])
        env['COMPARE'] = env['CNTL']
        env['PLOTTYPE'] = env['p_type']
        env['COLORTYPE'] = env['c_type']
        env['MG_MICRO'] = env['microph']
        env['TIMESTAMP'] = env['time_stamp']
        env['TICKMARKS'] = env['tick_marks']
        if env['custom_names'] == 'True':
            env['CASENAMES'] = 'True'
            env['CASE1'] = env['test_name']
            env['CASE2'] = env['cntl_name']
        else:
            env['CASENAMES'] = 'False'
            env['CASE1'] = 'null'
            env['CASE2'] = 'null'
            env['CNTL_PLOTVARS'] = 'null'
        env['test_in'] = env['test_path_climo'] + env['test_casename']
        env['test_out'] = env['test_path_climo'] + env['test_casename']
        env['cntl_in'] = env['cntl_path_climo'] + env['cntl_casename']
        env['cntl_out'] = env['cntl_path_climo'] + env['cntl_casename'] 

        env['seas'] = []
        if env['plot_ANN_climo'] == 'True':
            env['seas'].append('ANN')
        if env['plot_DJF_climo'] == 'True':
            env['seas'].append('DJF')
        if env['plot_MAM_climo'] == 'True':
            env['seas'].append('MAM')
        if env['plot_JJA_climo'] == 'True':
            env['seas'].append('JJA')
        if env['plot_SON_climo'] == 'True':
            env['seas'].append('SON')

        # Significance vars
        if env['significance'] == 'True':
            env['SIG_PLOT'] = 'True'
            env['SIG_LVL'] = env['sig_lvl']
        else:
            env['SIG_PLOT'] = 'False'
            env['SIG_LVL'] = 'null'
        
        # Set the rgb file name
        env['RGB_FILE'] = env['DIAG_HOME']+'/rgb/amwg.rgb'
        if 'default' in env['color_bar']:
            env['RGB_FILE'] = env['DIAG_HOME']+'/rgb/amwg.rgb'
        elif 'blue_red' in env['color_bar']:
            env['RGB_FILE'] = env['DIAG_HOME']+'/rgb/bluered.rgb'
        elif 'blue_yellow_red' in env['color_bar']:
            env['RGB_FILE'] = env['DIAG_HOME']+'/rgb/blueyellowred.rgb'

        # If SE grid, convert to lat/lon grid
        scomm.sync()
        regrid_script = 'regridclimo.ncl'
        # Convert Test Case
        if (env['CAM_DYCORE'] == 'se' or env['test_regrid'] == 'True'):
            # get list of climo files to regrid
            climo_files = glob.glob( env['test_path_climo']+'/*.nc')
            # partition the climo files between the ranks so each rank will get a portion of the list to regrid
            local_climo_files = scomm.partition(climo_files, func=partition.EqualStride(), involved=True)
            for climo_file in local_climo_files:
                print ('Regridding ',climo_file)
                diagUtilsLib.atm_regrid(climo_file, regrid_script, env['test_res_in'], env['test_res_out'], env)
        # Convert CNTL Case
        if (env['cntl_regrid'] == 'True'):
            # get list of climo files to regrid
            climo_files = glob.glob( env['cntl_path_climo']+'/*.nc')
            # partition the climo files between the ranks so each rank will get a portion of the list to regrid
            local_climo_files = scomm.partition(climo_files, func=partition.EqualStride(), involved=True)
            for climo_file in local_climo_files:
                print ('Regridding ',climo_file)
                diagUtilsLib.atm_regrid(climo_file, regrid_script, env['cntl_res_in'], env['cntl_res_out'], env)


        # Set Paleo variables
        env['PALEO'] = env['paleo']
        if env['PALEO'] == 'True':
            env['DIFF_PLOTS'] = env['diff_plots']
            # Test coastlines
            env['MODELFILE'] = env['test_path_climo']+'/'+env['test_casename']+'_ANN_climo.nc'
            env['LANDMASK'] = env['land_mask1']
            env['PALEODATA'] = env['test_path_climo']+'/'+env['test_casename']
            if scomm.is_manager():
                rc, err_msg = cesmEnvLib.checkFile(env['PALEODATA'],'read')
                if not rc:
                    diagUtilsLib.generate_ncl_plots(env,'plot_paleo.ncl')
            env['PALEOCOAST1'] = env['PALEODATA']
            # Cntl coastlines
            env['MODELFILE'] = env['cntl_path_climo']+'/'+env['cntl_casename']+'_ANN_climo.nc'
            env['LANDMASK'] = env['land_mask2']
            env['PALEODATA'] = env['cntl_path_climo']+'/'+env['cntl_casename']
            if scomm.is_manager():
                rc, err_msg = cesmEnvLib.checkFile(env['PALEODATA'],'read')
                if not rc:
                    diagUtilsLib.generate_ncl_plots(env,'plot_paleo.ncl')
            env['PALEOCOAST2'] = env['PALEODATA']
        else:
            env['PALEOCOAST1'] = 'null' 
            env['PALEOCOAST2'] = 'null'
            env['DIFF_PLOTS'] = 'False'

        env['USE_WACCM_LEVS'] = 'False'

        scomm.sync()

        return env

    def run_diagnostics(self, env, scomm):
        """ call the necessary plotting routines to generate diagnostics plots
        """
        super(modelVsModel, self).run_diagnostics(env, scomm)
        scomm.sync()

        # setup some global variables
        requested_plot_sets = list()
        local_requested_plots = list()
        local_html_list = list()

        # all the plot module XML vars start with 'set_'  need to strip that off
        for key, value in env.iteritems():
            if   ("wset_"in key and (value == 'True' or env['all_waccm_sets'] == 'True')):
                requested_plot_sets.append(key)
            elif ("cset_"in key and (value == 'True' or env['all_chem_sets'] == 'True')):
                requested_plot_sets.append(key)
            elif ("set_" in key and (value == 'True' or env['all_sets'] == 'True')):
                if ("wset_" not in key and "cset_" not in key):
                    requested_plot_sets.append(key)
        
        scomm.sync()

        # partition requested plots to all tasks
        # first, create plotting classes and get the number of plots each will created 
        requested_plots = {}
        set_sizes = {}
        plots_weights = []
        for plot_set in requested_plot_sets:
            requested_plots.update(atm_diags_plot_factory.atmosphereDiagnosticPlotFactory(plot_set,env))
        for plot_id,plot_class in requested_plots.iteritems(): 
            if hasattr(plot_class, 'weight'):
                factor = plot_class.weight
            else:
                factor = 1
            plots_weights.append((plot_id,len(plot_class.expectedPlots)*factor))
        # partition based on the number of plots each set will create
        local_plot_list = scomm.partition(plots_weights, func=partition.WeightBalanced(), involved=True)  

        timer = timekeeper.TimeKeeper()
        # loop over local plot lists - set env and then run plotting script         
        #for plot_id,plot_class in local_plot_list.interitems():
        timer.start(str(scomm.get_rank())+"ncl total time on task")
        for plot_set in local_plot_list:
            timer.start(str(scomm.get_rank())+plot_set)
            plot_class = requested_plots[plot_set]
            # set all env variables (global and particular to this plot call
            plot_class.check_prerequisites(env)
            # Stringify the env dictionary
            for name,value in plot_class.plot_env.iteritems():
                plot_class.plot_env[name] = str(value)
            # call script to create plots
            for script in plot_class.ncl_scripts:
                diagUtilsLib.generate_ncl_plots(plot_class.plot_env,script)
                plot_class.plot_env['NCDF_MODE'] = 'write'
                plot_class.plot_env['VAR_MODE'] = 'write'
            timer.stop(str(scomm.get_rank())+plot_set) 
        timer.stop(str(scomm.get_rank())+"ncl total time on task")
        scomm.sync() 
        print(timer.get_all_times())
        w = 0
        for p in plots_weights:
            if p[0] in local_plot_list:
                w = w + p[1]
        print(str(scomm.get_rank())+' weight:'+str(w))

        # set html files
        if scomm.is_manager():
            env['HTML_HOME'] = env['DIAG_HOME']+'/html/model1-model2/'
            # Get web dir name and create it if it does not exist
            web_dir = '{0}/{1}-{2}'.format(env['test_path_diag'], env['test_casename'], env['cntl_casename'])
            if not os.path.exists(web_dir):
                os.makedirs(web_dir)
            # Copy over some files needed by web pages
            if not os.path.exists(web_dir+'/images'):
                os.mkdir(web_dir+'/images')
            diag_imgs = glob.glob(env['DIAG_HOME']+'/html/images/*')
            for img in diag_imgs:
                shutil.copy(img,web_dir+'/images/')
          
            # Create set dirs, copy plots to set dir, and create html file for set 
            requested_plot_sets.append('sets') # Add 'sets' to create top level html files
            for plot_set in requested_plot_sets:
                 if 'set_5' == plot_set or 'set_6' == plot_set:
                     glob_set = plot_set.replace('_','')
                     plot_set = 'set5_6'
                 elif 'set_1' == plot_set:
                     glob_set = 'table_'
                     plot_set = plot_set.replace('_','') 
                 elif 'sets' == plot_set:
                     set_dir = web_dir + '/' 
                 else:
                     plot_set = plot_set.replace('_','')
                     glob_set = plot_set
                 if 'sets' not in plot_set: #'sets' is top level, don't create directory or copy images files
                     set_dir = web_dir + '/' + plot_set
                     # Create the plot set web directory
                     if not os.path.exists(set_dir):
                         os.makedirs(set_dir) 
                     # Copy plots into the correct web dir
                     glob_string = env['test_path_diag']+'/'+glob_set+'*'
                     imgs = glob.glob(glob_string) 
                     if imgs > 0:
                         for img in imgs:
                             new_fn = set_dir + '/' + os.path.basename(img)
                             os.rename(img,new_fn)
                 # Copy/Process html files
                 if 'sets' in plot_set:
                     orig_html = env['HTML_HOME']+'/'+plot_set 
                 else:
                     orig_html = env['HTML_HOME']+'/'+plot_set+'/'+plot_set 
                 create_html.create_plotset_html(orig_html,set_dir,plot_set,env)

            # Remove any plotvar netcdf files that exists in the diag directory
            if env['save_ncdfs'] == 'False':
                cesmEnvLib.purge(env['test_path_diag'], '.*\.nc')

            if len(env['WEBDIR']) > 0 and len(env['WEBHOST']) > 0 and len(env['WEBLOGIN']) > 0:
                # copy over the files to a remote web server and webdir 
                diagUtilsLib.copy_html_files(env)
            else:
                print('Web files successfully created in directory {0}'.format(env['test_path_climo']))
                print('The env_diags_atm.xml variable WEBDIR, WEBHOST, and WEBLOGIN were not set.')
                print('You will need to manually copy the web files to a remote web server.')

            print('*******************************************************************************')
            print('Successfully completed generating atmosphere diagnostics model vs. model plots')
            print('*******************************************************************************')
            
        scomm.sync()

