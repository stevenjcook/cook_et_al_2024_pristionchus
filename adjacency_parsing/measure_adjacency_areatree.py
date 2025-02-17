"""
measure_adjacency_areatree.py

##this is and updated version of measure_adjacency.py that uses the areatree data structure and employs multiprocessing to speed up analysis of layers. 
Original code from Brittin et al 2021. https://github.com/cabrittin/parsetrakem2


Synposis:
   python measure_adjaceny.py trakem2 fout [OPTIONS]

Parameters:
    trakem2 (str):  The file location of the trakem2 file
    fout (str): The file location of the xml file to which data will be written
    -p, --pixel_radius (int): Pixel radius to classify adjacent boundary points
                (default is 10)
    -t, --area_thresh (int): Arear lists smaller than the area thresh are excluded
                from processing (default is 200 px^2)
    -s, --scale_bounding_box (float): Scales the bounding box. Set to greater than 1
                to ensure that all adjacent boundaries are identified in the preprocessing
                step of looking for overlapping boundary boxes. (default is 1.1)
    -n, --nprox (int): Number of CPU(s) used to process each layer. (default is 1)
    -l, --layers (str): Specify which layers to process. Separate multiple layers
                 by a ','. Make sure to use the layer names in the trakem2 file. 
                 If not specified, then all layers will be processed. 


Examples:
  General use:
     python measure_adjacency.py /path/to/trakem2 /path/to/xml

  Increase number of CPUs
     python measure_adjacency.py /path/to/trakem2 /path/to/xml -n 2

  Specify layers to be processed
     python measure_adjacency.py /path/to/trakem2 /path/to/xml -l LAYER1,LAYER2,LAYER3
   

"""
import sys
import os
import argparse
import multiprocessing_on_dill as mp
from multiprocessing import Pool
import time
from lxml import etree
import itertools




from parsetrakem2 import ParseTrakEM2

def process_overlap(o, P):
    return P.batch_compute_adjacency(o, pixel_radius=params.pixel_radius)


def process_layer(l, P, params):
    print(f'Processing layer: {l}')
    parser = etree.XMLParser(remove_blank_text=True, huge_tree=True, recover=True)
    P.xml = etree.parse(P.trakem2, parser)
    B = P.get_boundaries_in_layer(l, area_thresh=params.area_thresh,
                                  scale_bounding_box=params.scale_bounding_box)
    overlap = P.get_overlapping_boundaries(B)
    adj = P.batch_compute_adjacency(overlap, pixel_radius=params.pixel_radius)
    return adj


def time_string(_seconds):
    day = _seconds // (24 * 3600)
    _seconds = _seconds % (24 * 3600)
    hour = _seconds // 3600
    _seconds %= 3600
    minutes = _seconds // 60
    _seconds %= 60
    seconds = _seconds
    return "%d:%d:%d:%d" % (day, hour, minutes, seconds)

def submit_batch(P,o,pixel_radius):
    adj = P.batch_compute_adjacency(o,pixel_radius)
    return adj
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('trakem2',
                        action="store",
                        help="TrakEM2 file")

    parser.add_argument('fout',
                        action = 'store',
                        help = "Output file")

    parser.add_argument('-p','--pixel_radius',
                        dest = 'pixel_radius',
                        action="store",
                        required = False,
                        default = 10,
                        type = int,
                        help = ("Boundaries separated by distances less than or "
                                "equal to the pixel radius are classified as "
                                "adjacent. DEFAULT = 10."))
    
    parser.add_argument('-t','--area_thresh',
                        dest = 'area_thresh',
                        action = 'store',
                        required = False,
                        default = 200,
                        type = int,
                        help = ("Area lists less than area_thresh are not "
                                "considered in the adajancency analysis. "
                                "DEFAULT = 200. "))

    parser.add_argument('-s','--scale_bounding_box',
                        dest = 'scale_bounding_box',
                        action = 'store',
                        required = False,
                        default = 1.1,
                        type = float,
                        help = ("Adjusts the search radius by scaling the "
                                "area list bounding boxes. DEFAULT = 1.1. "))
    
    parser.add_argument('-n','--nproc',
                        dest = 'nproc',
                        action = 'store',
                        required = False,
                        default = 1,
                        type = int,
                        help = ("Number of jobs if running "
                                "in multiprocessor mode. DEFAULT = 1.")
                        )
    
    parser.add_argument('-l','--layers',
                        dest = 'layers',
                        action = 'store',
                        required = False,
                        default = None,
                        help = ("Specifiy which layers to analyze. "
                                "Separate layers names by ',' e.g. LAYER1,LAYER2,.. "
                                "Must use layer name specified in "
                                "//t2_patch/@title in TrakEM2 file."))

    
    params = parser.parse_args()

    print('TrakEM2 file: %s' %params.trakem2)
    print('Writing to file: %s' %params.fout)
    print('Running %d jobs' %params.nproc) 
    print('Loading TrakEM2 file...')
    P = ParseTrakEM2(params.trakem2)
    P.get_layers()
    layers_list = [f"'{layer}'" for layer in P.layers]

    # Write layers to a text file
    with open('layers_output.txt', 'w') as f:
        f.write(', '.join(layers_list))
    print('Extracted %d layers.' %(len(P.layers)))

    P.get_area_lists()
    print('Extracted %d area lists.' %(len(P.area_lists))) 
    if params.layers:
        print('Analyzing layers: %s' %params.layers)
        layers = params.layers.split(',')
    else:
        print('Analyzing all layers.')
        layers = sorted(P.layers.keys())
    

    #Set up xml if file if it does not exist
    if not os.path.isfile(params.fout):
        data = etree.Element('data')
        xml_out = etree.tostring(data,pretty_print=False)
        with open(params.fout,'wb') as fout:
            fout.write(xml_out)
            
    #Open xml file
    tree = etree.parse(params.fout)
    root = tree.getroot()

    #Add layers not previously analyzed
    curr_layers = [l.get('name') for l in root.findall('layer')]
    for l in layers:
        if l in curr_layers:
            xlayer = root.find("layer[@name='%s']" %l)
            root.remove(xlayer)
        _l = etree.SubElement(root,'layer')
        _l.set('name',l)
        root.append(_l) 
    xml_out = etree.tostring(tree,pretty_print=False)
    with open(params.fout,'wb') as fout:
            fout.write(xml_out)


    print('Processing layers...')
    N = len(layers)
    print(layers)
    idx = 0
    __end = '\r'
    time0 = time.time()
    
    if params.nproc == 1:
        adjacencies = [process_layer(l, P) for l in layers]
    else:
        time1 = time.time()
        with Pool(processes=params.nproc) as pool:
            adjacencies = pool.starmap(process_layer, [(l, P, params) for l in layers])

    for l, adj in zip(layers, adjacencies):
        xlayer = root.find("layer[@name='%s']" %l)
        print(idx)
        for (b1,b2,_adj) in adj:
            xarea = etree.SubElement(xlayer,'area')
            cell1 = etree.SubElement(xarea,'cell1')
            cell1.text = b1.name
            cell2 = etree.SubElement(xarea,'cell2')
            cell2.text = b2.name
            idx1 = etree.SubElement(xarea,'index1')
            idx1.text = str(b1.index)
            idx2 = etree.SubElement(xarea,'index2')
            idx2.text = str(b2.index)     
            xadj = etree.SubElement(xarea,'adjacency')
            xadj.text = str(_adj)             
            
        idx += 1
        if idx == N: __end = '\n'
        proc_time = time_string(time.time() - time0)
        print("Processed %d/%d layers. Last layer processed: %s. "
              "Found %d adjacencies. " 
              "Time to process last layer: %2.3f sec. "
              "Total processing time: %s. "
              %(idx,N,l,len(adj),time.time() - time1,proc_time),end=__end)
    
        xml_out = etree.tostring(tree,pretty_print=False)
        with open(params.fout,'wb') as fout:
            fout.write(xml_out)
    print('Finished!')


