"""U02's separate fresh job namespace, using the project-native launch bridge."""
from tools import t01_crop_jobs as jobs
from tools import t01_board_export_jobs as directory
from tools.pcb_workspace import WORK,require_storage

MANAGED=WORK/'operator_routes/u02_board/managed'


def configure():
    require_storage();jobs.MANAGED=MANAGED


def intake(value):
    configure()
    if jobs.launcher_ready().get('u02_board')!='native-u02/1':raise ValueError('NATIVE_LAUNCHER_UPDATE_REQUIRED: close launcher Terminal and reopen tools/Start_T01_Native_Launcher.command once; no U02 job started')
    return directory.native_intake(value,action='u02_directory_intake',task_scope='u02-board')
