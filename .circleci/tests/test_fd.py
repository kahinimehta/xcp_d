from xcp_d.workflow.postprocessing import init_censoring_wf
from xcp_d.interfaces.prepostcleaning import censorscrub
import os
import pandas as pd


def test_fd():
    bold_file = '/Users/kahinim/Desktop/XCP_data/fmriprep/sub-99964/ses-10105/func/sub-99964_ses-10105_task-rest_acq-singleband_space-MNI152NLin6Asym_res-2_desc-preproc_bold.nii.gz'
    mask = '/Users/kahinim/Desktop/XCP_data/fmriprep/sub-99964/ses-10105/func/sub-99964_ses-10105_task-rest_acq-singleband_space-MNI152NLin6Asym_res-2_desc-brain_mask.nii.gz'
    confounds_tsv = '/Users/kahinim/Desktop/XCP_data/fmriprep/sub-99964/ses-10105/func/sub-99964_ses-10105_task-rest_acq-singleband_desc-confounds_timeseries.tsv'
    test_wf = init_censoring_wf(
        mem_gb=6,
        TR=0.8,
        head_radius=50,
        omp_nthreads=1,
        dummytime=0,
        fd_thresh=0.5,
        name='test_censoringwf',
        custom_conf=None)
    # Run workflow to see if it passes basic test
    inputnode = test_wf.get_node("inputnode")
    inputnode.inputs.bold = bold_file
    inputnode.inputs.bold_mask = mask
    inputnode.inputs.confound_file = confounds_tsv
    test_wf.run()


test_fd()  # Call the function


def test_fd_interface():  # Checking results
    input_file = '/Users/kahinim/Desktop/FD_test/fmriprep/sub-99964/ses-10105/func/sub-99964_ses-10105_task-rest_acq-singleband_space-MNI152NLin6Asym_res-2_desc-preproc_bold.nii.gz'
    mask = '/Users/kahinim/Desktop/FD_test/fmriprep/sub-99964/ses-10105/func/sub-99964_ses-10105_task-rest_acq-singleband_space-MNI152NLin6Asym_res-2_desc-brain_mask.nii.gz'
    confounds_tsv = '/Users/kahinim/Desktop/FD_test/fmriprep/sub-99964/ses-10105/func/sub-99964_ses-10105_task-rest_acq-singleband_desc-confounds_timeseries.tsv'
    df = pd.read_table(confounds_tsv)
    # Replace confounds tsv values with values that should be omitted
    df["trans_x"][1:4] = [6, 8, 9]
    df["trans_y"][5:8] = [7, 8, 9]
    df["trans_z"][9:12] = [12, 8, 9]
    print(df["trans_z"][9:12])  # Confirming that the df values are changed as expected
    tmpdir = '/Users/kahinim/Desktop/FD_test'  # So we can see results
    os.chdir(tmpdir)
    confounds_tsv = "edited_" + confounds_tsv.split('/func/')[1]  # Rename with same convention as initial confounds tsv
    df.to_csv(confounds_tsv, sep='\t', index=False)
    # Run workflow
    cscrub = censorscrub()
    # cscrub.inputs.bold_file = bold_file
    cscrub.inputs.in_file = input_file
    cscrub.inputs.TR = 0.8
    cscrub.inputs.fd_thresh = 0.5
    cscrub.inputs.fmriprep_conf = confounds_tsv
    cscrub.inputs.mask_file = mask
    cscrub.inputs.time_todrop = 0
    cscrub.inputs.head_radius = 50
    cscrub.run()


test_fd_interface()  # Call the function