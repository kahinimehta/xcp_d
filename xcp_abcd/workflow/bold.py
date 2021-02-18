# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
post processing the bold
^^^^^^^^^^^^^^^^^^^^^^^^
.. autofunction:: init_boldpostprocess_wf

"""
import sys
import os
from copy import deepcopy
import nibabel as nb
from nipype import __version__ as nipype_ver
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu
from nipype import logging
from ..utils import collect_data
from ..interfaces import computeqcplot
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from  ..utils import bid_derivative
from ..interfaces import  FunctionalSummary

from  ..workflow import (init_fcon_ts_wf,
    init_post_process_wf,
    init_compute_alff_wf,
    init_3d_reho_wf)
from .outputs import init_writederivatives_wf

LOGGER = logging.getLogger('nipype.workflow')

def init_boldpostprocess_wf(
     bold_file,
     lowpass,
     highpass,
     smoothing,
     head_radius,
     params,
     custom_conf,
     omp_nthreads,
     scrub,
     dummytime,
     output_dir,
     fd_thresh,
     template='MNI152NLin2009cAsym',
     num_bold=1,
     layout=None,
     name='bold_postprocess_wf',
      ):
    TR = layout.get_tr(bold_file)

    workflow = Workflow(name=name)
   
    # get reference and mask
    mask_file,ref_file = _get_ref_mask(fname=bold_file)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['bold_file','mni_to_t1w','ref_file','bold_mask','cutstom_conf']),
        name='inputnode')
    
    inputnode.inputs.bold_file = str(bold_file)
    
    inputnode.inputs.ref_file = str(ref_file)
    inputnode.inputs.bold_mask = str(mask_file)
    inputnode.inputs.custom_conf = str(custom_conf)


    outputnode = pe.Node(niu.IdentityInterface(
        fields=['processed_bold', 'smoothed_bold','alff_out','smoothed_alff', 
                'reho_out','sc207_ts', 'sc207_fc','sc407_ts','sc407_fc',
                'gs360_ts', 'gs360_fc','gd333_ts', 'gd333_fc','qc_file']),
        name='outputnode')

    
    # get the mem_bg size for each workflow
    
    mem_gbx = _create_mem_gb(bold_file)
    clean_data_wf = init_post_process_wf(mem_gb=mem_gbx['timeseries'], TR=TR,
                    head_radius=head_radius,lowpass=lowpass,highpass=highpass,
                    smoothing=smoothing,params=params,
                    scrub=scrub,dummytime=dummytime,fd_thresh=fd_thresh,
                    name='clean_data_wf') 
    
    
    fcon_ts_wf = init_fcon_ts_wf(mem_gb=mem_gbx['timeseries'],
                 t1w_to_native=_t12native(bold_file),bold_file=bold_file,
                 template=template,name="fcons_ts_wf")
    
    alff_compute_wf = init_compute_alff_wf(mem_gb=mem_gbx['timeseries'], TR=TR,
                   lowpass=lowpass,highpass=highpass,smoothing=smoothing, surface=False,
                    name="compute_alff_wf" )

    reho_compute_wf = init_3d_reho_wf(mem_gb=mem_gbx['timeseries'],smoothing=smoothing,
                       name="afni_reho_wf")
    
    write_derivative_wf = init_writederivatives_wf(smoothing=smoothing,bold_file=bold_file,
                    params=params,scrub=scrub,surface=None,output_dir=output_dir,dummytime=dummytime,
                    lowpass=lowpass,highpass=highpass,TR=TR,omp_nthreads=omp_nthreads,
                    name="write_derivative_wf")
   
    workflow.connect([
        (inputnode,clean_data_wf,[('bold_file','inputnode.bold')]),
        
        (inputnode,clean_data_wf,[('bold_mask','inputnode.bold_mask')]),                     

        (inputnode,fcon_ts_wf,[
                               ('ref_file','inputnode.ref_file'),
                               ('mni_to_t1w','inputnode.mni_to_t1w') ]),
        (clean_data_wf, fcon_ts_wf,[('outputnode.processed_bold','inputnode.clean_bold'),]),

        (inputnode,alff_compute_wf,[('bold_mask','inputnode.bold_mask')]),
        (clean_data_wf, alff_compute_wf,[('outputnode.processed_bold','inputnode.clean_bold')]),

        (inputnode,reho_compute_wf,[('bold_mask','inputnode.bold_mask'),]),
        (clean_data_wf, reho_compute_wf,[('outputnode.processed_bold','inputnode.clean_bold')]),
        
    
        (clean_data_wf,outputnode,[('outputnode.processed_bold','processed_bold'),
                                   ('outputnode.smoothed_bold','smoothed_bold')]),
        (alff_compute_wf,outputnode,[('outputnode.alff_out','alff_out'),
                                      ('outputnode.smoothed_alff','smoothed_alff')]),
        (reho_compute_wf,outputnode,[('outputnode.reho_out','reho_out')]),
        (fcon_ts_wf,outputnode,[('outputnode.sc207_ts','sc207_ts' ),('outputnode.sc207_fc','sc207_fc'),
                        ('outputnode.sc407_ts','sc407_ts'),('outputnode.sc407_fc','sc407_fc'),
                        ('outputnode.gs360_ts','gs360_ts'),('outputnode.gs360_fc','gs360_fc'),
                        ('outputnode.gd333_ts','gd333_ts'),('outputnode.gd333_fc','gd333_fc')]),
        ])
    if custom_conf:
        workflow.connect([
         (inputnode,clean_data_wf,[('custom_conf','inputnode.custom_conf')]),
        ])

    qcreport = pe.Node(computeqcplot(TR=TR,bold_file=bold_file,dummytime=dummytime,
                       head_radius=head_radius), name="qc_report")
    workflow.connect([
        (inputnode,qcreport,[('bold_mask','mask_file')]),
        (clean_data_wf,qcreport,[('outputnode.processed_bold','cleaned_file'),
                            ('outputnode.tmask','tmask')]),
        (qcreport,outputnode,[('qc_file','qc_file')]),
           ])
    
    workflow.connect([
        (clean_data_wf, write_derivative_wf,[('outputnode.processed_bold','inputnode.processed_bold'),
                                   ('outputnode.smoothed_bold','inputnode.smoothed_bold')]),
        (alff_compute_wf,write_derivative_wf,[('outputnode.alff_out','inputnode.alff_out'),
                                      ('outputnode.smoothed_alff','inputnode.smoothed_alff')]),
        (reho_compute_wf,write_derivative_wf,[('outputnode.reho_out','inputnode.reho_out')]),
        (fcon_ts_wf,write_derivative_wf,[('outputnode.sc207_ts','inputnode.sc207_ts' ),
                                ('outputnode.sc207_fc','inputnode.sc207_fc'),
                                ('outputnode.sc407_ts','inputnode.sc407_ts'),
                                ('outputnode.sc407_fc','inputnode.sc407_fc'),
                                ('outputnode.gs360_ts','inputnode.gs360_ts'),
                                ('outputnode.gs360_fc','inputnode.gs360_fc'),
                                ('outputnode.gd333_ts','inputnode.gd333_ts'),
                                ('outputnode.gd333_fc','inputnode.gd333_fc')]),
        (qcreport,write_derivative_wf,[('qc_file','inputnode.qc_file')]),
        
         ])
    functional_qc = pe.Node(FunctionalSummary(bold_file=bold_file,tr=TR),
                name='qcsummary', run_without_submitting=True)
        
    ds_report_qualitycontrol = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='qualitycontrol',source_file=bold_file, datatype="figures"),
                  name='ds_report_qualitycontrol', run_without_submitting=True)

    ds_report_preprocessing = pe.Node(
        DerivativesDataSink(base_directory=output_dir, desc='preprocessing',source_file=bold_file, datatype="figures"),
                  name='ds_report_preprocessing', run_without_submitting=True)
    ds_report_postprocessing = pe.Node(
        DerivativesDataSink(base_directory=output_dir,source_file=bold_file, desc='postprocessing', datatype="figures"),
                  name='ds_report_postprocessing', run_without_submitting=True)
    
    workflow.connect([
        (qcreport,ds_report_preprocessing,[('raw_qcplot','in_file')]),
        (qcreport,ds_report_postprocessing ,[('clean_qcplot','in_file')]), 
        (qcreport,functional_qc,[('qc_file','qc_file')]),
        (functional_qc,ds_report_qualitycontrol,[('out_report','in_file')])
    ])

    return workflow 

def _create_mem_gb(bold_fname):
    bold_size_gb = os.path.getsize(bold_fname) / (1024**3)
    bold_tlen = nb.load(bold_fname).shape[-1]
    mem_gbz = {
        'derivative': bold_size_gb,
        'resampled': bold_size_gb * 4,
        'timeseries': bold_size_gb * (max(bold_tlen / 100, 1.0) + 4),
    }

    return mem_gbz

def _get_ref_mask(fname):
    directx = os.path.dirname(fname)
    filename = filename=os.path.basename(fname)
    filex = filename.split('preproc_bold.nii.gz')[0] + 'brain_mask.nii.gz'
    filez = filename.split('_desc-preproc_bold.nii.gz')[0] +'_boldref.nii.gz'
    mask = directx + '/' + filex
    ref = directx + '/' + filez
    return mask, ref

def _t12native(fname):
    directx = os.path.dirname(fname)
    filename = filename=os.path.basename(fname)
    fileup = filename.split('desc-preproc_bold.nii.gz')[0].split('space-')[0]
    
    t12ref = directx + '/' + fileup + 'from-T1w_to-scanner_mode-image_xfm.txt'
    
    return t12ref


class DerivativesDataSink(bid_derivative):
    out_path_base = 'xcp_abcd'