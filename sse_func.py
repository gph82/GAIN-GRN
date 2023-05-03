#sse_func.py
# Functions to be used by gain_classes.py and workflow.py
# For reading/writing stuff, parsing alignments, plotting etc.

import glob
import numpy as np

#### READ BLOCK ####

def read_sse_loc(file): 
    '''
    STRIDE output file parsing function, returns the FULL sequence of SSE data (N->C direction)
    Parameters : 
        file : str, required
            STRIDE file to be read. 
    Returns 
        sseDict : dict
            Dictionary containing all SSE with respective names and intervals by residue
    '''
    sseDict = {}

    with open(file) as f:

        for l in f.readlines():

            if l.startswith("LOC"):     # ASG is the per-residue ASSIGNMENT of SSE
                                        # LOC is already grouped from [start - ]
                items = l.split(None)   # [24] has the SSE one-letter code
                sse, first, last = items[1], int(items[3]), int(items[6])

                if sse not in sseDict.keys():
                    sseDict[sse] = [(first, last)]
                else:
                    sseDict[sse].append((first,last))
    return sseDict

def read_sse_asg(file):
    '''
    STRIDE output file parsing function, used for modified stride files contaning outliers as lowercase letters (H - h, G - g)
    Parameters : 
    file : str, required
            STRIDE file to be read. 
    Returns 
        residue_sse : dict
            DICT containing a sequence of all letters assigned to the residues with the key being the present residue
    '''

    with open(file) as f:
        asgs = [l for l in f.readlines() if l.startswith("ASG")]

    first_res = int(asgs[0].split(None)[3])
    last_res = int(asgs[-1].split(None)[3]) 
    residue_sse = {k:"X" for k in range(first_res, last_res+1)}

    for l in asgs:              # ASG is the per-residue ASSIGNMENT of SSE
                                # LOC is already grouped from [start - ]
        items = l.split(None)   # [24] has the SSE one-letter code
        # Example lines:
        # items[i]:
        #  0    1 2    3    4    5             6         7         8         9        10
        #ASG  THR A  458  453    E        Strand   -123.69    131.11       4.2      ~~~~
        #ASG  SER A  459  454    E        Strand    -66.77    156.86      10.4      ~~~~
        # 3 is the PDB index, 4 is the enumerating index, this is crucial for avoiding offsets, always take 3
        residue_sse[int(items[3])] = items[5]
        # if there is missing keys, just label them "X", since these are residues skipped by AlphaFold2 (i.e. "X")
        
    return residue_sse

def read_stride_angles(file, filter_letter=None):
    '''
    STRIDE output file parsing function, used for modified stride files contaning outliers as lowercase letters (H - h, G - g)
    Parameters : 
    file : str, required
            STRIDE file to be read. 
    filter_letter : str, optional
            Filters entries to match a pre-assigneed secondary structure letter (E, H, ...) --> items[3]
    Returns 
        residue_sse : dict
            DICT containing PHI and PSI float values for each residue number (PDB) as key.
    '''
    # Example lines:
    # items[i]:
    #  0    1 2    3    4    5             6         7         8         9        10
    #
    #ASG  SER A  459  454    E        Strand    -66.77    156.86      10.4      ~~~~
    # 3 is the PDB index, 4 is the enumerating index, this is crucial for avoiding offsets, always take 3  
    with open(file) as f:
        asgs = [l for l in f.readlines() if l.startswith("ASG")]

    angles = {}
    for l in asgs:
        items = l.split(None)   # [24] has the SSE one-letter code
        if filter_letter is None or filter_letter == items[5]:
            angles[int(items[3])] = [float(items[7]), float(items[8])]

    return angles

def get_angle_outlier(sse:list, stride_file:str, phi_mean_sd, psi_mean_sd, psi_prio=True):
    # For strand outliers, prioritize PSI over PSI - with precalculated values of PHI and PSI mean+SD:
    angles = read_stride_angles(stride_file)
    phipsi = [phi_mean_sd, psi_mean_sd]
    sse_angles = np.array([ angles[i] for i in range(sse[0],sse[1]) ])

    if psi_prio:
        order = [0,1]
    else:
        order = [1,0]
    for i in order:
        xangles = [ x+360 if x<0 else x for x in sse_angles[:,i]] # remove negative values for wrapping in negative angle values
        max_deviance = np.argmax( [abs(x - phipsi[i][0]) for x in xangles] )
        #print(f"{abs(xangles[max_deviance] - phipsi[i][0]) = } | {2*phipsi[i][1] = }")
        if abs(xangles[max_deviance] - phipsi[i][0]) > 2*phipsi[i][1]:
            return sse[0]+max_deviance
    # If not outside 2 sigma, return None.
    return None

def read_seq(file, return_name=False):
    '''
    Read a sequence from a FASTA file, return sequence name if specified.
    Parameters:
        file : str, required
            The FASTA file to be read
        return_name : bool, optional
            return sequence name if true. Default = False
    Returns:
        seq : str
            The sequence of the FASTA file
        name : str
            The name of the sequence specified in the first line.
    '''
    with open(file) as f:
        for line in f:
            if line.startswith(">"): 
                if return_name == False:
                    continue
                name = line[1:].strip()
            else: 
                seq = line.strip(" \t\r\n")
                if return_name == False:
                    return seq

                return name, seq

def read_multi_seq(file):
    '''
    Build a sequences object from a FASTA file contaning multiple sequences.

    Parameters:
        file : str, required
            The FASTA file to be read
    Returns:
        sequences : object
        A list contaning one tuple per sequence with (name, sequence)
    '''
    with open(file) as f:
        data = f.read()
        entries = data.strip().split(">")
        entries = list(filter(None, entries))
    sequences = np.empty([len(entries)], dtype=tuple)

    for i, entry in enumerate(entries):
        name, sequence = entry.strip().split("\n")
        sequences[i] = (name, sequence)

    return sequences

def read_alignment(alignment, cutoff=-1):
    '''
    Load all the data from an alignment into a matrix, stopping at the cutoff column
    
    Parameters:
        alignment :     str, required
            An Alignment file in FASTA format to be read
        cutoff :        int, required
            The index of the last alignment column to be read

    Returns:
        sequences : dict
            a dictionary with {sequence_name}:{sequence} as items
    '''
    sequences = {}

    with open(alignment) as f:

        data = f.read()
        seqs = data.split(">")

        for seq in seqs[1:]: # First item is empty

            sd = seq.splitlines()
            try: 
                sd[0] = sd[0].split("/")[0]
            except: 
                pass

            sequences[sd[0]] = "".join(sd[1:])[:cutoff] 

    return sequences

def read_quality(jal): 
    '''
    extracts ONLY BLOSUM62 quality statements from the specified annotation file
    This jal file can be generated by exporting Annotation from an Alignment in JALVIEW

    Parameters:
        jal : str, required
            A JALVIEW exported annotation file. The file extension is arbitrary.

    Returns:
        cut_data : list
            A list contaning all the Blosum62 quality values per alignment column
    '''
    with open(jal) as annot:

        data = None

        for line in annot:

            if "Blosum62" in line[:200]:
                data = line.strip(" \t\r\n").split("|")
            else: 
                continue

        if not data: # Sometimes, BLOSUM62 data is not contained in the annotation file

            print(f"ERROR: Blosum62 indication not found in {jal}")
            return None

    # Process the raw data into a list
    cut_data=[]
    [cut_data.append(float(i.split(",")[1][:5])) for i in data if len(i) > 0]

    return cut_data

#### DETECTING BLOCK ####

def detect_GPS(alignment_indices, gps_minus_one):
    '''
    Detects the GPS residue at the specified index of the Alignment
    This is not very robust - the quality depends on the respecitve MSA

    Parameters:
        alignment_indices : list, required
            A list of the alignment indices contained in a target protein (all integer)
        gps_minus_one : int, required
            The alignment index of the (most conserved) GPS-1 residue right C-terminal of the cleavage site

    Returns:
        gps_center : int
            The residue index of the GAIN domain residue matching the specified alignment index
    '''
    try: 
        gps_center = np.where(alignment_indices == gps_minus_one)[0][0]
        return gps_center
    except IndexError:
        print("[WARNING] sse_func.detect_GPS: GPS-1 column is empty. Returning empty for alternative Detection.")
        print(f"\t{gps_minus_one  = }\n\t{alignment_indices[-15:] = }")
        return None

def detect_signchange(signal_array, exclude_zero=False, check=False):
    ''' 
    Detect signchanges in a smoothened numerical signal array
    Can be adjusted to view "0" as separate sign logic or not.

    Parameters:
        signal_array : np.array, required
            A 1D-array containing the signal values. This should already be smoothened by np.concolve
        exclude_zero : bool, optional
            Specifies whether to view 0 as a separate entity for a sign change. Defalt: False
        check :        bool, optional
            Specifies whether to check the occurrence of a signchange along the wrap of last and first array value.
            Deault: False

    Returns:
        boundaries :   np.array
            An array with the indices of the detected sign changes
    '''
    asign = np.sign(signal_array)   # -1 where val is negative, 0 where val is zero, 1 where val is positive.
    sz = asign == 0                 # A boolean list where True means that asign is zero

    if exclude_zero == True:        #  Exclude where the value is EXACTLY zero, 0 has an unique sign [-x,0,x]
        while sz.any(): 
            asign[sz] = np.roll(asign, 1)[sz]
            sz = asign == 0
    
    signchange = ((np.roll(asign, 1) - asign) != 0).astype(int)
    boundaries = np.asarray(signchange != 0).nonzero()[0]
    if boundaries.shape[0] == 0:
        print("WARNING: No boundaries detected!")
        return None
    # CHECK:
    # Special case. If the first and last value of the array have a different sign,
    # boundaries[0] = 0, which should be discarded depending on the signal. 
    # Keep only the value where val[i] != 0
    if boundaries[0] == 0 and check == True:
        #print("NOTE: array wrap signchange detected. Checking with Flag check = True.")
        if signal_array[0] == 0:       # There is no SSE begin @ residue 0, otherwise its ok
            boundaries = np.delete(boundaries, 0)
        if boundaries.shape[0]%2 != 0: # If the length is now uneven, means that last res. is SSE
            boundaries = np.append(boundaries, len(signal_array))
    
    return boundaries

def find_boundaries(sse_dict, seq_len, bracket_size=50, domain_threshold=50, coil_weight=0, truncate_N=None):
    '''
    make an array with the length of the sequence
    via np.convolve generate the freq of alpha-helix vs beta-sheets, 
    assigning 1 to Helices, -1 to sheets
    The boundaries are the two most C-terminal crossing point 
    of the convolve function of x > 0 to x < 0, respectively

    Parameters:
        sse_dict :      dict, required
            A dictionary with the SSE of the specified region
        seq_len :       int, required
            The total length of the target sequence
        bracket_size :  int, optional
            The size of the bracket used for convolving the signal. default = 50
        domain_threshold : int, optional
            Minimum size of a helical block to be considered Subdomain A candidate. default = 50
        coil_weight :   float, optional
            The numerical value assigned to unordered residues, used for faster "decay" of helical blocks if <0
            values of 0 to +0.2 may be tried
        truncate_N:     int, optional, default: None
            If set to True, the Domain will be immedately truncated $truncate_N residues N-terminally of the most N-terminal helix. 

    Returns:
        gain_start : int
            The most N-terminal residue index of the GAIN domain
        subdomain_boundary : int
            The residues index of the Subdomain boundary between A (helical) and B (sheet)
    '''
    # Check if the dictionary even contains AlphaHelices, and also check for 310Helix
    helices = []
    sheets = []
    if 'AlphaHelix' not in sse_dict.keys() or 'Strand' not in sse_dict.keys():
        print("This is not a GAIN domain.")
        return None, None

    [helices.append(h) for h in sse_dict['AlphaHelix']]

    if '310Helix' in sse_dict.keys(): 
        [helices.append(h) for h in sse_dict['310Helix']]

    [sheets.append(s) for s in sse_dict['Strand']]
    
    # coil_weight can be used to add a "decay" of unstructured residues into the signal
    # in that case, a value like +0.1 is alright, this will sharpen helical regions
    scored_seq = np.full([seq_len], fill_value=coil_weight)

    for element_tuple in helices:
        scored_seq[element_tuple[0]:element_tuple[1]] = -1
    for element_tuple in sheets:
        scored_seq[element_tuple[0]:element_tuple[1]] = 1

    # Smooth the SSE signal with np.convolve 
    signal = np.convolve(scored_seq, np.ones([bracket_size]), mode='same')
    boundaries = detect_signchange(signal, exclude_zero=True)

    ### Find the interval with most negative values
    # First, check if there are valid boundaries!
    if boundaries is None:
        print('No boundaries detected. Returning empty.')
        return None, None
    
    helical_counts = np.zeros([len(boundaries)-1],dtype=int)

    for k in range(len(boundaries)-1):
        start, end = boundaries[k], boundaries[k+1]
        sliced_array = scored_seq[start:end]
        helical_counts[k] = np.count_nonzero(sliced_array == -1)

    # Find the "first" (from C-terminal) helical section larger than the threshold
    # maxk is the size of the helical region
    maxk = None
    # reverse the helical array
    rev_helical = helical_counts[::-1]

    for rev_count, hel_len in enumerate(rev_helical):
        if hel_len >= domain_threshold:
            maxk = len(helical_counts)-(rev_count+1)
            break

    #print(f"[DEBUG] sse_func.find_boundaries : \n\tFound Helix boundary with the following characteristics: {maxk = } {helical_counts[maxk] = }(new variant)")
    # if it finds maxk, store the valies denoting the helical block for further refinement
    if maxk is None:
        print("No Helical segment satisfying the domain_size found: Maximum helical segment =", max(helical_counts))
        return None, None
    
    gain_start, initial_boundary = boundaries[maxk], boundaries[maxk+1]

    if truncate_N is not None:
        for i, res in enumerate(scored_seq[gain_start:]):
            if res == -1:
                print(f"[NOTE] Overwriting initial {gain_start = } with {i-truncate_N}.")
                gain_start = gain_start+i-truncate_N
                break
    # After it found the most likely helical block, adjust the edge of that, designate as Subdomain A
    # adjust the subdomain boundary to be in the middle of the loop between Helix and Sheet

    helix_end = initial_boundary
    sheet_start = initial_boundary
    
    if scored_seq[sheet_start] == 1:
        while True:
            sheet_start -= 1 # go left to find the end of the current sheet
            if scored_seq[sheet_start] != 1:
                break
    else:
        while True:
            sheet_start  += 1 # go right to find the start of the first Subdomain B sheet
            if scored_seq[sheet_start] == 1:
                break

    if scored_seq[helix_end] != -1: # go left to find the end of the last Subdomain A Helix
        while True:
            helix_end -= 1
            if scored_seq[helix_end] == -1:
                break
    else:   
        while True:
            helix_end += 1 # go right to find the end of the last Subdomain A Helix
            if scored_seq[helix_end] != -1:
                break
    nocoil = True
    if coil_weight != 0:
        nocoil = False
    # Final sanity check to see if there are any SSE left in the interval between helix_end and sheet_start
    #if np.count_nonzero(scored_seq[helix_end+1:sheet_start]) > 1 : # This threw a warning when coil_weight != 0
    if not nocoil and 1 in scored_seq[helix_end+1:sheet_start]:
        print("[WARNING] sse_func.find_boundaries : "
            "There are still secondary-structure associated residues within the Subdomain connecting loop. Please check if this is within limits:\n"
            f"{scored_seq[helix_end+1:sheet_start]}")

    subdomain_boundary = (helix_end+sheet_start) // 2  # The subdomain bondary is the middle of the two SSEs limiting the sections
    #if subdomain_boundary - gain_start >= domain_threshold:
    #print(f"DEBUG: find_boundaries returning {boundaries[maxk] = }, {boundaries[maxk+1] = }")
    return gain_start, subdomain_boundary


def sse_sequence2bools(sse_dict:dict):
    '''
    Create a dictionary containing the actually detected alpha helices and beta sheets for all residues in sse_dict, 
    using lower_case mode detection and the spacing variable
    '''
    #print(f"[DEBUG] sse_func.sse_sequence2bools:\n\t{sse_dict = }")
    len = max(sse_dict.keys())
    hel_signal = np.zeros(shape=[len], dtype=int)
    she_signal = np.zeros(shape=[len], dtype=int)
    
    for res, assigned_sse in sse_dict.items():
        if assigned_sse.upper() == "H" or assigned_sse.upper() == "G":
            hel_signal[res] = 1
        elif assigned_sse.upper() == "E":
            she_signal[res] = 1

    return hel_signal, she_signal

def count_domain_sses(domain_start, domain_end, tuple_list=None, spacing=1, minimum_length=3, sse_bool=None, debug=False):
    if debug:
        print(f"[DEBUG] sse_func.count_domain_sses CALLED WITH: \n\t tuple list",
              tuple_list, "sse_bool", sse_bool)
    # provide either sse_bool or tuple_list
    if sse_bool is None:
        parsed_sses = []
        if debug: 
            print(f"[DEBUG] sse_func.count_domain_sses : No sse_bool specified. Constructing from:\n\t{tuple_list = } \n\t{domain_start = } {domain_end = }")
        # First, check if the SSE limits exceed the provided Domain boundary (sort of a sanity check)
        for sse in tuple_list:
            if sse[0] >= domain_start and sse[1] <= domain_end:
                #print(f"[DEBUG] sse_func.count_domain_sses : {sse = }")
                parsed_sses.append(sse)
            
        sse_bool = np.zeros(shape=[domain_end], dtype=bool)
        for element_tuple in parsed_sses:
            if debug: 
                print(f"{element_tuple = }")
            sse_bool[element_tuple[0]:element_tuple[1]+1] = 1 # THE LAST NUMBER OF THE TUPLE IN LIST IS INCLUDED!
                                                              #        0  1  2  3  4  5  6  7  8  9 10 11  ...
                                                              # (1,9) [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, ...]
            #print(f"[DEBUG] sse_func.count_domain_sses : {element_tuple = }")
    
    # Otherwise SSE_BOOL has been passed and is used directly
    # Truncate the SSE BOOL by setting everything outside the boundaries to zero.
    sse_bool[:domain_start] = 0
    up_edges = []
    down_edges = []
    #break_residues = []

    for i in range(len(sse_bool)-1):
        if sse_bool[i] and not sse_bool[i+1]: # [.. 1 0 ..]
            down_edges.append(i+1)
        if not sse_bool[i] and sse_bool[i+1]: # [.. 0 1 ..]
            up_edges.append(i+1)
    down_edges.append(len(sse_bool))

    if debug:
        print(f"[DEBUG] sse_func.count_domain_sses :\n\t{up_edges = }\n\t{down_edges = }")
    # Remove all segments between down-edge and up-edge where count(0) <= spacing
    # remove zero-segments whose length is smaller than $spacing
    i = 0
    n_elements = len(up_edges)
    while i < n_elements-1:
        if debug: print(f"{i = } {n_elements = }\n\t{up_edges = }\n\t{down_edges = }")
        unordered_length = up_edges[i+1] - down_edges[i]
        if unordered_length <= spacing:
            #breaks = list(range(down_edges[i], up_edges[i+1]))
            #break_residues.append(breaks)
            del up_edges[i+1]
            del down_edges[i]
            n_elements -= 1
            continue
        # If this is a unique element, append empty breaks.
        #break_residues.append([])
        i += 1
    
    # With the cleaned up lists of up_edges and down_edges, get all elements satisfying minium_length and within boundaries.
    intervals = []
    for i in range(n_elements):
        element_length = down_edges[i] - up_edges[i]
        if element_length < minimum_length:
            continue
        if up_edges[i] < domain_end:
            intervals.append([up_edges[i], down_edges[i]-1])
    if debug:
        print(f"[DEBUG] sse_func.count_domain_sses : RETURNING \n\t{intervals = }")#\n\t{break_residues = }")

    return np.asarray(intervals)#, break_residues

def count_domain_sses_old(domain_start, domain_end, tuple_list=None, spacing=1, minimum_length=3, sse_bool=None):
    ''' 
    Count the total number of SSE in a given interval (domain_start-domain_end) 
    that are disrupted by max. {spacing} residues 

    Parameters:
        domain_start : int, required
            The residue index indicating the most N-terminal GAIN domain residue
        domain_end   : int, required
            The residue index indicating the most C-terminal GAIN domain reisdue
        tuple_list   : list, required
            A list fo tuples indicating start and end of each secondary structure element
            Can be extracted directly from any sse_dict
        spacing :       int, optional
            The number of unstructured residues tolerated within a single SSE
            default = 0, good results were retrieved with spacing=1 as well
        minimum_length : int_optional
            The minimum length of a helix to be counted as one.

    Returns:
        found_sses : numpy.array 
            2D Array with three values per entry
            first val indexes SSE element detected
            second val is start, end residue index
            third val is indices of break residues

    '''
    if sse_bool is None:
        parsed_sses = []
        #print(f"[DEBUG] sse_func.count_domain_sses : \n\t{tuple_list = } \n\t{domain_start = } {domain_end = }")
        # First, check if the SSE limits exceed the provided Domain boundary (sort of a sanity check)
        for sse in tuple_list:
            if sse[0] >= domain_start and sse[1] <= domain_end:
                #print(f"[DEBUG] sse_func.count_domain_sses : {sse = }")
                parsed_sses.append(sse)
            
        sse_bool = np.zeros(shape=[domain_end])
        for element_tuple in parsed_sses:
            sse_bool[element_tuple[0]:element_tuple[1]+1] = 1
            #print(f"[DEBUG] sse_func.count_domain_sses : {element_tuple = }")
    
    #print(f"[DEBUG] sse_func.count_domain_sses : {sse_bool = }")
    # Otherwise SSE_BOOL has been passed and is used directly
    else:
        # Truncate the SSE BOOL by setting everything outside the boundaries to zero.
        sse_bool[:domain_start] = 0
    if spacing != 0:
        sse_signal = np.convolve(sse_bool, np.ones([spacing+1]), mode='same')
    else:
        sse_signal = sse_bool
    
    #print(f"[DEBUG")
    sse_boundaries = detect_signchange(sse_signal, check=True)
  
    if sse_boundaries is None:
        print("There are no SSE found in this Subsection.")
        return None

    break_residues = [] # Where for the fuzzy detection, residues where the spacing is applied are listed

    found_sses = sse_boundaries.reshape([sse_boundaries.shape[0]//2,2])
    filtered_sses = []
    #print(f"[DEBUG] sse_func.count_domain_sses : After signal detection:\n{found_sses}")
    
    # re-value SSE boundaries for exact boundaries if spacing != 0
    for i in range(found_sses.shape[0]):
        bool_element = sse_bool[found_sses[i,0]:found_sses[i,1]]
        # Check for break residues in the bool element by projecting it onto the sse_bool and seeing where it is zero
        # eliminating the first and last element
        breaks = [res for res in np.where(bool_element[1:-1] == 0)[0]]
        #print(type(breaks))
        # Check for minimum SSE length - if not satisfied, delete entries from found_sses
        if len(bool_element) < (minimum_length+spacing): 
            #print(f"[DEBUG] sse_func.count_domain_sses : Element too small: {bool_element=}")
            continue

        filtered_sses.append([found_sses[i,0]+np.nonzero(bool_element)[0][0], 
                               found_sses[i,0]+np.nonzero(bool_element)[0][-1] ]) 
        break_residues.append(breaks)
    #print(f"DEBUG: After adjusting:\n{found_sses}")
    # ADJUST TO MATCH TO ONE-INDEXED ARRAY AS PROVIDED
    #print(f"[DEBUG] sse_func.count_domain_sses : \n\t Final filtered SSES {np.asarray(filtered_sses) = }, \n {np.asarray(break_residues,dtype=object) = }")
    return np.asarray(filtered_sses), break_residues

def get_sse_type(sse_types, sse_dict):
    '''
    Get a list of all SSEs of a type (type/s as str / list) in sse_dict within
    a given Interval. Returns [] if the given types are not contained in sse_dict.keys()

    Parameters:
        sse_types : (list of str) or str, required
            Specifies the key(s) in the dict to be looked up
        sse_dict : dict, required
            The dectionary to be parsed

    Returns:
        sse_tuples : list
            A list of tuples containing all residue indices with start and end
            of each SSE corresponding to the specified types
    '''
    sse_tuples = []
    
    if type(sse_types) == list:
        for sse in sse_types:
            if sse not in sse_dict.keys(): 
                if sse != "310Helix":
                    print(f"KeyNotFound: {sse}") # Is is frequently the case that there are no 310Helices, nothing to worry there. print no Note.
                continue
            sse_tuples = sse_tuples + sse_dict[sse]
        return sse_tuples
    
    elif type(sse_types) == str:
        if sse_types not in sse_dict.keys():
            print(f"KeyError: no {sse_types} in dict.keys()")
            return []
        return sse_dict[sse_types]
    
    print(f"Error: Key(s) not found {sse_types} (get_sse_type)")
    return []

def find_stride_file(name, path="stride_out/*_0.stride"):
    '''
    Finds the STRIDE file in a collection of stride files,
    then reads SSE info from this found file via read_sse_loc()
    Used in the base dataset calculation

    Parameters:
        name : str, required
            The name of the sequence, corresponding to the search string
        path : str, optional
            The glob.glob() string to find the STRIDE file collection. default = stride_out/*_0.stride

    Returns:
        sse_dict : dict
            The dictionary containng SSE data as in read_sse_loc()
    '''
    stride_files = glob.glob(path) #_0 indicates that only the best model SSE data is evaluated
    strides = [st for st in stride_files if name in st]

    if len(strides) == 0:
        print("ERROR: Stride files not found in here. {name = }")
        return None

    sse_dict = read_sse_loc(strides[0])
    return sse_dict

def find_the_start(longseq, shortseq): 
    '''
    Find the start of a short sequence in a long sequence.
    Pattern matching while the longseq from an MSA may also contain "-" as in Alignments
    This enables to extract the sequence from an alignment where is might be spaced out

    Parameters : 
        longseq : str, required
            A sequence string of one-letter amino acids and the "-" character, as in parsed from a FASTA alignment
        shortseq : str, required
            The short sequence being an exact slice of the long sequence, without "-"

    Returns :
        start : int
            The index of the first shortseq residue in longseq. Used for parsing alingment indices. 
    '''
    cat_seq = "".join(shortseq)
    findstring = cat_seq[:15] # The First 15 residues of N-->C direction as matching string
    id_array = np.arange(len(longseq)) # assign column indices to longseq, starting @ zero
    map_matrix = np.ones([len(longseq)], dtype=bool)

    for i, char in enumerate(longseq):
        if char == "-":
            map_matrix[i]=False 
    
    longseq_array = np.array([char for char in longseq]) #array of the FULL Seq
    
    filter_seq = longseq_array[map_matrix == True] # longseq without all "-" character
    filter_id = id_array[map_matrix == True] #  The indices of non- "-" characters are preserved here
    
    locator = "".join(filter_seq).find(findstring) #print(f"DEBUG: {''.join(filter_seq) = } {locator = }")
    start = filter_id[locator] #print("Found the Start @", start)
    
    return start

def get_indices(name, sequence, alignment_file, aln_cutoff, alignment_dict=None, truncation_map=None, aln_start_res=None):
    '''
    Find a sequence in the alignment file, output a number of corresponding alignment indices for each residue in sequence

    Parameters:
        name : str, required
            The sequence name, must correspond to name in the alignment file
        sequence : numpy array, required
            The one-letter coded amino acid sequence
        alignment_file : str, required
            The alignment file containing all the information and name
        aln_cutoff : int, required
            The integer value of the last alignment residue column to be parsed
        alignment_dict : dict, optional
            If specified, skips loading the alignment file and directly looks up the sequences in the dictionary. Improves Performance
        aln_start_res : int, optional
            If known, specify the start column of the first residue in the Alignment.
    Returns:
        mapper : list
            A list of alignment indices for each residue index of the sequence
    '''
    #print(f"[DEBUG] sse_func.get_indices : {sequence.shape = }")
    mapper = np.zeros([sequence.shape[0]],dtype=int) # Initialize the mapper for output
    #print(f"[DEBUG] sse_func.get_indices : {mapper.shape = }")
    if not alignment_dict:
        alignment_dict = read_alignment(alignment_file, aln_cutoff)
    
    # PATCH: If the name ends on ".fa", eliminate that.
    try: nam = name.split(".fa")[0]
    except: nam = name

    #print(f"[DEBUG] sse_func.get_indices : \n\t{nam = }, is it in the dict? {nam in alignment_dict.keys()}")
    try:
        align_seq = alignment_dict[nam]#[::-1] # make the reference alignment reverse to compare rev 2 rev
    except KeyError:
        print("[WARNING]: Sequence not found. If this is unintended, check the Alignment file!\n", nam)
        return None 

    align_len = len(align_seq) 
    #print(f"[DEBUG] {align_len = }, {nam = }, {truncation_map.shape}")

    if aln_start_res is None:
        try: 
            aln_start_res = find_the_start(alignment_dict[nam], sequence) 
            # Finds the first index matching the sequence end and outputs the index
            #print(f"Found the start! {aln_start_res = }")#\n {align_seq = }")
        except: 
            print("Did not find the Sequence! - No start. Unknown ERROR!")
            return None
    
    align_index = aln_start_res 
    #print("".join(sequence), len(sequence))
    for i,residue in enumerate(sequence):   # For each residue, enter the While loop
        #print("[DEBUG] current residue:", i, residue, "@", align_index)
        # If the current residue is truncated, skip to the next one.
        if truncation_map is not None and truncation_map[i]:
            mapper[i] = -1 #(integer for now! DEBUGGABLE!)
            print(f"NOTE: Skipping truncated residue @ {residue}{i+1}")
            continue

        while align_index < len(align_seq):                         # True ; To find the residue
            if residue == align_seq[align_index]:
                mapper[i] = align_index     # If it is found, note the index
                align_index += 1            # advance the index to avoid double counted identical resiudes (i.e. "EEE")
                break
            elif align_seq[align_index] != "-": 
                print("WARNING! OUT OF PLACE RESIDUE FOUND:", align_seq[align_index], "@", align_index, "while searching for", residue, i)
            align_index += 1
    # return the matching list of alignment indices for each Sequence residue
    #print(f"[DEBUG] sse_func.get_indices : mapper constructed successfully.")
    #print(f"{mapper}")
    return mapper

def get_quality(alignment_indices, quality_arr):
    '''
    Parses through the quality array and extracts the matching columns of alignment indices to assign each residue a quality value.
    
    Parameters:
        alignment_indices : list, required
            A list of alignment indices that will be read from
        quality_arr : array, (1D), required
            An array containing the quality value for each column in the underlying alignment,
            can be substituted for any kind of signal used for assigning anchor residues
    
    Returns:
        index_qualities : list
            A list of values matching each index in alignment_indices
    '''     
    index_qualities = np.zeros([len(alignment_indices)])
    
    for i,position in enumerate(alignment_indices):
        index_qualities[i] = quality_arr[position]
    
    return index_qualities

#### CUTTING AND TRUNCATING ####

def cut_sse_dict(start, end, sse_dict):
    '''
    Truncate all SSE in the complete dictionary read from STRIDE to SSE only within the GAIN domain
    
    Parameters:
        start : int, required
            Residue index of the most N-terminal domain residue
        end : int, required
            Residue index of the most C-terminal domain residue
        sse_dict : dict, required
            The full SSE dictionary containing all SSE information

    Returns:
        new_dict : dict
            The dictionary containing only SSE within the domain boundaries.
    '''
    new_dict = {}
    
    for key in sse_dict.keys():

        new_sse_list = []

        for item in sse_dict[key]:

            if item[0] > end or item[1] < start:
                continue
            # Should not happen, but just in case, truncate SSE to the GAIN boundary 
            # if they exceed them
            elif item[0] < start: 
                item = (start, item[1])
            elif item[1] > end:
                item = (item[0], end)
                
            new_sse_list.append(item)
        
        # Some structures (like specific Turns) may not be within the GAIN. Skip that.
        if len(new_sse_list) == 0:
            continue
        
        # Read the list into the dictionary    
        new_dict[key] = new_sse_list     

    return new_dict

def get_subdomain_sse(sse_dict:dict, subdomain_boundary:int, start:int, end:int, residue_sse:dict, stride_outlier_mode=False, debug=False):
    '''
    Fuzzy detection of Helices in Subdomain A and Sheets in Subdomain B
    Count them and return their number + individual boundaries

    Parameters:
        sse_dict : dict, required
            Dict containing all SSE information about the GAIN domain
        subdomain_boundary : int, required
            The residue index of the residue denoting the subdomain boundary
        start : int, required
            Residue index of the most N-terminal domain residue
        end : int, required
            Residue index of the most C-terminal domain residue
        stride_outlier_mode : bool, optional

    Returns:
        alpha : 
            2D array of dimension ((number of sse), (start, end)) for alpha helices in Subdomain A
        beta : 
            2D array of dimension ((number of sse), (start, end)) for beta sheets in Subdomain B
        alpha_breaks:
            array of breaking points in the SSE definiton. Used for disambiguating close SSE in Subdomain A
        beta_breaks:
            array of breaking points in the SSE definiton. Used for disambiguating close SSE in Subdomain B
    '''
    helices = get_sse_type(["AlphaHelix", "310Helix"], sse_dict)
    sheets = get_sse_type("Strand", sse_dict)
    if debug:
        print(f"[DEBUG] sse_func.get_subdomain_sse : \n\t {helices = } \n\t {sheets = } \n\t {subdomain_boundary = }")

    # Parse boundaries, relevant for other uses of this function like enumerating other sections
    if subdomain_boundary == None:
        helix_upperbound = end
        sheet_lowerbound = start
    else:
        helix_upperbound = subdomain_boundary
        sheet_lowerbound = subdomain_boundary

    if stride_outlier_mode == False:    
        alpha = count_domain_sses(start,helix_upperbound, helices, spacing=1, minimum_length=3, debug=debug) # PARSING BY SSE DICTIONARY
        beta = count_domain_sses(sheet_lowerbound, end, sheets, spacing=1, minimum_length=2, debug=debug) # 
    
    if stride_outlier_mode == True:
        # This version should be generall the case for GAIN domains evaluated in GainCollection.__init__()
        hel_bool, she_bool = sse_sequence2bools(residue_sse)
        alpha = count_domain_sses(start, helix_upperbound, helices, spacing=1, minimum_length=3, sse_bool=hel_bool, debug=debug) # PARSING BY SSE-SEQUENCE
        beta = count_domain_sses(sheet_lowerbound, end, sheets, spacing=1, minimum_length=2, sse_bool=she_bool, debug=debug) # 
    if debug:
        print(f"[DEBUG] sse_func.get_subdomain_sse : \n\t{stride_outlier_mode = }\n\t {alpha = } \n\t {beta = }")
    return alpha, beta

#### NAMING SCHEME ####

def name_sse(sse_dict, subdomain_boundary, start, end, residue_sse, debug=False):
    '''
    THIS IS A ROUGH NAMING SCHEME AND >NOT THE NOMENCLATURE<, BUT THIS CAN BE PERFORMED WITHOUT THE UNDERLYING DATASET!
    generate a name map from the information about the GAIN domain
    For this initial map, count the Helices and sheets separately and index N-->C
    Use the fuzzy function based on the spacing in sse_func.count_domain_sses

    Parameters:
        sse_dict : dict, required
            Dict containing all SSE information about the GAIN domain
        subdomain_boundary : int, required
            The residue index of the residue denoting the subdomain boundary
        start : int, required
            Residue index of the most N-terminal domain residue
        end : int, required
            Residue index of the most C-terminal domain residue

    Returns:
        name_arr : list
            A list containing the label of the naming scheme for each residue of the GAIN domain
    '''
    alpha, beta, _, _ = get_subdomain_sse(sse_dict, subdomain_boundary, start, end, residue_sse, debug=debug)

    name_arr = np.empty([end-start], dtype='<U16')
    is_helix = np.zeros([end-start], dtype=bool)
    is_sheet = np.zeros([end-start], dtype=bool)

    if alpha is not None:
        for i, helix_tuple in enumerate(alpha):
            is_helix[helix_tuple[0]-start:helix_tuple[1]-start+1] = True
    for j, sheet_tuple in enumerate(beta):
        is_sheet[sheet_tuple[0]-start:sheet_tuple[1]-start+1] = True
    
    # get the individual name of each residue from N-->C based on whether it is a helix or sheet
    # or in-between
    helix_index = 0
    sheet_index = 0
    current_string = None
    is_sse = False
    
    myorder = reversed(range(end-start))

    for res in myorder:
        if is_sse == False: # case low - our residue was in a non-sheet + non-helix region
            
            if is_sheet[res] == True: # upper edge - we come into a sheet
                sheet_index += 1
                prefix = "S"
                is_sse = True
                current_string = f"{prefix}{sheet_index}" # update string
            elif is_helix[res] == True: # upper egde - we come into a helix
                helix_index += 1
                prefix = "H"
                is_sse = True
                current_string = f"{prefix}{helix_index}" # update string

        else: # high edge - we are within a SSE
            # lower edge - we come in to a SSE connecting region
            if is_helix[res] == False and is_sheet[res] == False: 
                is_sse = False
                if prefix == "H":
                    idx = f"{helix_index}-{helix_index+1}"
                elif prefix == "S":
                    idx = f"{sheet_index}-{sheet_index+1}"
                prefix = "L."+prefix
                current_string = f"{prefix}{idx}" # update string
        #print(f"DEBUG {is_sse}") 
        name_arr[res] = current_string
    # Clean up the populated string array:
    i = 0
    while True:
        #print(name_arr[i], name_arr[i][0])
        if name_arr[i][0] == "H":
            break
        name_arr[i] = None
        i+=1
    # The loop between the Subdomains is adressed separately
    if subdomain_boundary != None:
        i = subdomain_boundary - start
        j = subdomain_boundary - start
        while True:
            if name_arr[i][0] == "S":
                break
            name_arr[i] = "L.A/B"
            i+=1
        while True:
            if name_arr[j][0] == "H":
                break
            name_arr[i] = "L.A/B"
            j-=1

    return name_arr

#### Truncating MSA sequence from the map file

def truncate_sequence(map_file, sequence, right_threshold=801, max_size=700): 
    '''
    Truncate the sequence to only include residues contained within the alignment.
    
    Parameters:
        map_file : str, required
            The map file contaning the information from mafft --add
                map file structure:
                >{name}|species|residues
                    P, 139, 809
                    A, 140, 810
                    L, 141, 811
                    D, 142, -
                    R, 143, -
        sequence : str, required
            The full sequence of the protein
        right_threshold : int, optional
            right threshold denotes the rightmost alignment column that MUST be included. default = 801 = GPS+1
        max_size : int, optional
            The maximum size of the output sequence in case of AlphaFold2 size errors. Counts from C-terminus.
            default = 700

    Returns:
        sequence[left_threshold:last_residue] : list
            A truncated sequence containing only the residues within the alignment as denoted in the map file
    '''
    with open(map_file, "r") as m:

        data = m.readlines()

        init_flag = False
        beyond_right_threshold = False

    # Parse through the data
    for line in data:

        if line.startswith(">") or line.startswith("#"):
            continue

        items = line.strip().split(", ")
        # Fetch the start of the residues 
        if items[2].strip() != "-" and init_flag == False:
            print(f"NOTE: Alignment-fitting: initial residue {items[1]} @ column index {items[2]}!")
            init_flag = True
            first_residue = int(items[1])
        # Check if the threshold is satisfied for each following residue
        if items[2].strip() != "-" and int(items[2]) >= right_threshold:
            beyond_right_threshold = True
            last_residue = int(items[1])
        # Stop after threshold is reached and the first gap occurs
        if beyond_right_threshold == True and items[2].strip() == "-":
            last_residue = int(items[1])
            break

    print(f"NOTE: Alignment-fitting: Found fitted interval {first_residue} and {last_residue}.")
    # Truncate if the sequence is larger than the first alignment column assigns
    if last_residue - first_residue > max_size:
        left_threshold = last_residue - max_size
    else:
        left_threshold = 0 

    return sequence[left_threshold:last_residue]

#### MISCELLANEOUS FUNCTIONS

def write2fasta(sequence, name, filename):
    '''
    Construct a standard sequence fasta file

    Parameters:
        sequence: str, required
            The string of the one-letter amino acid sequence
        name:     str, required
            The name to be put into the header of the FASTA
        filename: str, required
            The file name'''
    with open(filename, 'w') as fa:
        fa.write(f'>{name}\n{sequence}')
    print(f'NOTE: Written {name} to fasta in {filename}.')

def make_anchor_dict(fixed_anchors, sd_boundary):
    '''
    Enumerate the secondary structures according to the nomenclature conventions, st
    - Separate both Subdomains A and B
    - Only label Helices in Subdomain A, Sheets in Subdomain B
    - The most C-terminal anchor will be alpha and increased from there in N->C direction

    Parameters : 
        fixed_anchors : list, required
            A list of anchor residues as alignment indices (integer)
        sd_boundary :   int,  required
            The integer value of the subdomain boundary from the alignment

    Return : 
        anchor_dict : dict
            the enumerated adressing of each anchor residue with greek letters
    '''
    anchor_dict = {}
    helices = [a for a in fixed_anchors if a < sd_boundary]
    sheets = [a for a in fixed_anchors if a > sd_boundary]
    for idx, h in enumerate(helices):
        anchor_dict[h] = "H"+str(idx+1)
    for idx, s in enumerate(sheets):
        anchor_dict[s] = "S"+str(idx+1)
    return anchor_dict

def create_indexing(gain_domain, anchors:dict, anchor_occupation:dict, anchor_dict:dict, outdir=None, offset=0, silent=False, split_mode='single',debug=False):
    ''' 
    Makes the indexing list, this is NOT automatically generated, since we do not need this for the base dataset
    Prints out the final list and writes it to file if outdir is specified
    
    Parameters
    ----------
    anchors : list, required
        List of anchors with each corresponding to an alignment index
    anchor_occupation : list, required
        List of Occupation values corresponding to each anchor for resolving ambiguity conflicts
    anchor_dict : dict, required
        Dictionary where each anchor index is assigned a name (H or S followed by a greek letter for enumeration)
    offfset : int,  optional (default = 0)
        An offsset to be incorporated (i.e. for offsetting model PDBs against UniProt entries)
    silent : bool, optional (default = False)
        opt in to run wihtout so much info.
    outdir : str, optional
        Output directory where the output TXT is going to be written as {gain_domain.name}.txt

    Returns
    ---------
    indexing_dir : dict
        A dictionary containing the residue indices for each assigned SSE and the GPS
    indexing_centers : dict
        A dictionary containing the XX.50 Residue for each assigned SSE
    named_residue_dir : dict
        A dictionary mapping individual consensus labels to their respective position.
    unindexed : list
        A list of detected SSE that remain unindexed.
    '''
    # recurring functional blocks used within this function

    def create_name_list(sse, ref_res, sse_name):
        ''' Creates a indexing list for an identified SSE with reference index as X.50,
            Also returns a tuple containing the arguments, enabling dict casting for parsing '''
        number_range = range(50+sse[0]-ref_res, 51+sse[1]-ref_res)
        name_list = [f"{sse_name}.{num}" for num in number_range]
        cast_values = (sse, ref_res, sse_name)
        return name_list, cast_values

    def indexing2longfile(gain_domain, nom_list, outfile, offset):
        ''' Creates a file where the indexing will be denoted line-wise per residue'''
        with open(outfile, "w") as file:
            file.write(gain_domain.name+"\nSequence length: "+str(len(gain_domain.sequence))+"\n\n")
            print("[DEBUG] GainDomain.create_indexing.indexing2longfile\n", nom_list, "\n", outfile)
            for j, name in enumerate(nom_list[gain_domain.start:]):
                file.write(f"{gain_domain.sequence[j]}  {str(j+gain_domain.start+offset).rjust(4)}  {name.rjust(7)}\n")

    def disambiguate_anchors(gain_domain, stored_anchor_weight, stored_res, new_anchor_weight, new_res, sse, coiled_residues, outlier_residues, mode='single'):
        #Outlier and Coiled residues are indicated as relative indices (same as sse, stored_res, new_res etc.)
        #print(f"[DEBUG] disambiguate_anchors: {stored_anchor_weight = }, {stored_res = }, {new_anchor_weight = }, {new_res = }, {sse = }")
        def terminate(sse, center_res, break_residues, include=False):
            #print(f"DEBUG terminate : {sse = }, {sse[0] = }, {sse[1] = }, {center_res = }, {adj_break_res = }")           
            # look from the center res to the N and C direction, find the first break residue
            # Return the new boundaries
            if include:
                terminal = 0
            if not include:
                terminal = -1

            n_breaks = [r for r in break_residues if r < center_res and r >= sse[0]]
            c_breaks = [r for r in break_residues if r > center_res and r <= sse[1]]
            
            if n_breaks != []:
                N_boundary = max(n_breaks) - terminal
            else:
                N_boundary = sse[0]
            
            if c_breaks != []:
                C_boundary = min(c_breaks) + terminal
            else:
                C_boundary = sse[1]
            
            return [N_boundary, C_boundary]

        # this mode indicates if the anchor will just be overwritten instead of split,
        #   this will be set to OFF if there are breaks between both anchors
        hasCoiled = False
        hasOutlier = False

        # GO THROUGH CASES DEPENDING ON PRESENT BREAKS

        # a) there are no break residues
        if coiled_residues == [] and outlier_residues == []:
            if new_anchor_weight > stored_anchor_weight:
                name_list, cast_values = create_name_list(sse, new_res, anchor_dict[gain_domain.alignment_indices[new_res]])
            else: 
                name_list, cast_values = create_name_list(sse, stored_res, anchor_dict[gain_domain.alignment_indices[stored_res]])
            
            return [(sse, name_list, cast_values)], False

        # b) check first if there is a Coiled residue in between the two conflicting anchors
        for coiled_res in coiled_residues:
            if stored_res < coiled_res and coiled_res < new_res:
                hasCoiled = True 
            if new_res < coiled_res and coiled_res < stored_res:
                hasCoiled = True

        # c) check if there is an outlier residue in between the two conflicting anchors
        for outlier_res in outlier_residues:
            if stored_res < outlier_res and outlier_res < new_res:
                hasOutlier = True 
            if new_res < outlier_res and outlier_res < stored_res:
                hasOutlier = True

        # If there are no breaks, take the anchor with higher occupation, discard the other.
        if hasCoiled == False and hasOutlier == False:
            if not silent: 
                print(f"DEBUG gain_classes.disambiguate_anchors : no break found between anchors, will just overwrite.")
            if new_anchor_weight > stored_anchor_weight:
                name_list, cast_values = create_name_list(sse, new_res, anchor_dict[gain_domain.alignment_indices[new_res]])
            else: 
                name_list, cast_values = create_name_list(sse, stored_res, anchor_dict[gain_domain.alignment_indices[stored_res]])
            
            return [(sse, name_list, cast_values)], False

        # If breaks are present, find the closest break_residue to the lower weight anchor
        if mode == 'single':
            # "SINGLE" mode: Go and find the split closest to the low-priority anchor. 
            #   Split there and include everything else (even other break residues) in the higher priority anchor segment
            if stored_anchor_weight > new_anchor_weight:
                lower_res = new_res
            else:
                lower_res = stored_res

            if hasCoiled:
                breaker_residues = coiled_residues
            if not hasCoiled:
                breaker_residues = outlier_residues
            print(f"{breaker_residues = }, {lower_res = }")

            lower_seg = terminate(sse, lower_res, breaker_residues, include= not hasCoiled)
            # The rest will be assigned the other SSE, including the breaker residue if it is not coiled:
            lower_n, lower_c = lower_seg[0], lower_seg[1]
            if hasCoiled:
                terminal = -1
            else:
                terminal = 0
            print(f"{sse = }")
            print(f"{sse[0]-lower_n = }, {sse[1]-lower_c = }")
            if sse[0]-lower_n > sse[1]-lower_c: # either should be 0 or positive. This case: lower_seg is C-terminal
                upper_seg = [sse[0], lower_n+terminal]
            else: # This case: lower_seg is N-terminal
                upper_seg = [lower_c-terminal, sse[1]]

            # Go in left and right direction, check where there is the first break
            breaker = None
            offset = 1
            while offset < 20:
                if lower_res + offset in breaker_residues:
                    offset_idx = breaker_residues.index(lower_res + offset)
                    breaker = lower_res + offset
                    break
                if lower_res - offset in breaker_residues:
                    offset_idx = breaker_residues.index(lower_res - offset)
                    breaker = lower_res - offset
                    break

                offset += 1 

            if breaker is None: 
                print("[ERROR] BREAKER residue not found.") 
                return None, None

            # Divide SSE via BREAKER into two segments, create two separate name_list instances for them
            # If the breaker was a coil, set terminal to 1 to exclude this residue; otherwise, include it.
            if hasCoiled:
                terminal = 1
            if not hasCoiled:
                terminal = 0
            seg_N = [sse[0],breaker_residues[offset_idx]-terminal]
            seg_C = [breaker_residues[offset_idx]+terminal, sse[1]]

            if stored_res < breaker:
                seg_stored = seg_N
                seg_new = seg_C
            else:
                seg_stored = seg_C
                seg_new = seg_N
            
            print(f"[TESTING] terminate :{upper_seg = } {lower_seg = }")
            print(f"[TESTING] terminate :{seg_stored = } {seg_new = } {breaker = }")

        if mode == 'double':
            # "DOUBLE" mode: from both sides of the anchor, find the closest breaker residue and terminate each of the new segments
            seg_stored = terminate(sse, stored_res, breaker_residues, include= not hasCoiled)
            seg_new = terminate(sse, new_res, breaker_residues, include= not hasCoiled)

        if not silent: 
            print(f"[NOTE] disambiguate_anchors: Split the segment into: {seg_stored = }, {seg_new = }")

        stored_name_list, stored_cast_values = create_name_list(seg_stored, stored_res, anchor_dict[gain_domain.alignment_indices[stored_res]])
        new_name_list, new_cast_values = create_name_list(seg_new, new_res, anchor_dict[gain_domain.alignment_indices[new_res]])

        #print(f"[NOTE] disambiguate_anchors: Successful SSE split via BREAKER residue @ {breaker}")

        return [(seg_stored, stored_name_list, stored_cast_values),(seg_new, new_name_list, new_cast_values)], True # True indicates if lists were split or not!

    def cast(nom_list, indexing_dir, indexing_centers, sse_x, name_list, cast_values):
        #print(f"DEBUG CAST",sse_x, name_list, cast_values)
        nom_list[sse_x[0]+gain_domain.start : sse_x[1]+1+gain_domain.start] = name_list
        indexing_dir[cast_values[2]] = cast_values[0] # all to sse 
        indexing_centers[cast_values[2]+".50"] = cast_values[1] # sse_res where the anchor is located
        return nom_list, indexing_dir, indexing_centers

### END OF FUNCTION BLOCK

    # Initialize Dictionaries
    indexing_dir = {}
    indexing_centers = {}
    named_residue_dir = {}
    unindexed = []
    # One-indexed Indexing list for each residue, mapping for the actual residue index
    nom_list = np.full([gain_domain.end+1], fill_value='      ', dtype='<U7')

    for i,typus in enumerate([gain_domain.sda_helices, gain_domain.sdb_sheets]): # Both types will be indexed separately
        # Go through each individual SSE in the GAIN SSE dictionary
        for idx, sse in enumerate(typus):
            # Get first and last residue of this SSE
            #try:
            first_col = gain_domain.alignment_indices[sse[0]]
            #except: continue
            # Error correction. Sometimes the detected last Strand exceeds the GAIN boundary.
            if debug: print(f"DEBUG {sse[1] = }; {gain_domain.end-gain_domain.start = }, {len(gain_domain.alignment_indices) = }")
            if sse[1] > gain_domain.end-gain_domain.start-1:
                last_col = gain_domain.alignment_indices[-1]
                sse_end = sse[1]-1
            else:
                last_col = gain_domain.alignment_indices[sse[1]]
                sse_end = sse[1]

            exact_match = False                             # This is set to True, otherwise continue to Interval search
            fuzzy_match = False                             # Flag for successful Interval search detection
            ambiguous = False                               # Flag for ambiguity
            if debug:print(f"[DEBUG] GainDomain.create_indexing : \n{typus} No. {idx+1}: {sse}")
            if debug:print(f"[DEBUG] GainDomain.create_indexing : \n{first_col = }, {last_col = }")
            
            for sse_res in range(sse[0],sse_end+1):
                # Find the corresponding alignment index for that residue:
                if sse_res < len(gain_domain.alignment_indices):
                    sse_idx = gain_domain.alignment_indices[sse_res]
                else:
                    continue
                
                if sse_idx in anchors:

                    if exact_match == False:  
                        if debug: print(f"PEAK FOUND: @ {sse_res = }, {sse_idx = }, {anchor_dict[sse_idx]}")
                        #sse_name = anchor_dict[sse_idx]
                        anchor_idx = np.where(anchors == sse_idx)[0][0]
                        if debug: print(f"{np.where(anchors == sse_idx)[0] = }, {sse_idx = }, {anchor_idx = }")
                        stored_anchor_weight = anchor_occupation[anchor_idx]
                        #stored_anchor = anchors[anchor_idx]
                        stored_res = sse_res
                        name_list, cast_values = create_name_list(sse, sse_res, anchor_dict[sse_idx])
                        # name_list has the assignment for the SSE, cast_values contains the passed values for dict casting
                        exact_match = True
                        continue
                    ''' HERE is an ANCHOR AMBIGUITY CASE
                            There might occur the case where two anchors are within one SSE, 
                            check for present break residues in between the two anchors, 
                            > If there are some, eliminate that residue and break the SSE it into two.
                                >   If there are multiple break residues, use the one closest to the lower occupancy anchor
                            > If there is no break residue the anchor with highest occupation wins. '''
                    ambiguous = True
                    if not silent: 
                        print(f"[NOTE] GainDomain.create_indexing : ANCHOR AMBIGUITY in this SSE:")
                        print(f"\n\t {sse_idx = },")
                        print(f"\n\t {anchor_dict[sse_idx] = },")
                    # if the new anchor is scored better than the first, replace!

                    # Check for residues that have assigned "C" or "h" in GainDomain.sse_sequence
                    coiled_residues = []
                    outlier_residues = []
                    max_key = max(gain_domain.sse_sequence.keys())
                    for i in range(sse[0]+gain_domain.start, sse[1]+gain_domain.start+1):
                        if i > max_key:
                            if debug:
                                print("[DEBUG]: GainDomain.create_indexing. {i = } exceeded {max_key = }")
                            break
                        if gain_domain.sse_sequence[i] ==  "C":
                            coiled_residues.append(i-gain_domain.start)
                        if gain_domain.sse_sequence[i] == 'h':
                            outlier_residues.append(i-gain_domain.start)
                    if debug:
                        print(f"[DEBUG] GainDomain.create_indexing :\n\t{coiled_residues  = }\n\t{outlier_residues = }")
                    disambiguated_lists, isSplit = disambiguate_anchors(gain_domain,
                                                                        stored_anchor_weight=stored_anchor_weight,
                                                                        stored_res=stored_res,
                                                                        new_anchor_weight=anchor_occupation[np.where(anchors == sse_idx)[0][0]],
                                                                        new_res=sse_res,
                                                                        sse=sse,
                                                                        coiled_residues=coiled_residues,
                                                                        outlier_residues=outlier_residues,
                                                                        mode=split_mode)
                    if not silent: print(disambiguated_lists)
                    sse_adj, name_list, cast_values = disambiguated_lists[0]
                    if isSplit:
                        sse_adj_2, name_2, cast_2 = disambiguated_lists[1]
                        if not silent: print(f"[DEBUG] GainDomain.create_indexing : Found a split list:\n"
                            f"{sse_adj_2  = },\t{name_2 = },\t{cast_2 =  }")
                        nom_list, indexing_dir, indexing_centers = cast(nom_list, indexing_dir, indexing_centers, sse_adj_2, name_2, cast_2)
                        # Also write split stuff to the new dictionary
                        for entryidx, entry in enumerate(name_2): 
                            named_residue_dir[entry] = entryidx+sse_adj[0]+gain_domain.start
                    # if anchor_occupation[np.where(anchors == sse_idx)[0]] > stored_anchor_weight:
                    #    name_list, cast_values = create_name_list(sse, sse_res, anchor_dict[sse_idx])
            # if no exact match is found, continue to Interval search and assignment.
            if exact_match == False:
                # expand anchor detection to +1 and -1 of SSE interval
                ex_first_col = gain_domain.alignment_indices[sse[0]-1]
                try:
                    ex_last_col = gain_domain.alignment_indices[sse[1]+1]
                except:
                    ex_last_col = last_col
                # Construct an Interval of alignment columns corresp. to the SSE residues
                if debug:print(f"[DEBUG] GainDomain.create_indexing : \nNo exact match found: extindeing search.\n{typus} No. {idx+1}: {sse}")
                for peak in anchors: # Look if any peak is contained here
                    
                    if ex_first_col <= peak and ex_last_col >= peak:
                        fuzzy_match = True
                        if not silent: print(f"[DEBUG] GainDomain.create_indexing : Interval search found anchor @ Column {peak}")
                        # Find the closest residue to the anchor column index. N-terminal wins if two residues tie.
                        peak_dists = [abs(gain_domain.alignment_indices[res]-peak) \
                                                for res in range(sse[0], sse_end+1)]

                        ref_idx = peak_dists.index(min(peak_dists))
                        ref_res = range(sse[0], sse_end+1)[ref_idx]

                        if not silent: print(f"NOTE: GainDomain.create_indexing : Interval search found SSE:"
                                                f"{peak = }, {peak_dists = }, {ref_res = }. \n"
                                                f"NOTE: GainDomain.create_indexing : This will be named {anchor_dict[peak]}")

                        name_list, cast_values = create_name_list(sse, ref_res, anchor_dict[peak])

            # Finally, if matched, write the assigned nomeclature segment to the array
            
            if ambiguous == False and exact_match == True or fuzzy_match == True:
                nom_list, indexing_dir, indexing_centers = cast(nom_list, indexing_dir, indexing_centers, sse, name_list, cast_values)
                # Also cast to general indexing dictionary
                for namidx, entry in enumerate(name_list):
                    named_residue_dir[entry] = namidx+sse[0]+gain_domain.start
            elif ambiguous == True:
                nom_list, indexing_dir, indexing_centers = cast(nom_list, indexing_dir, indexing_centers, sse_adj, name_list, cast_values)
                # Also cast to general indexing dictionary
                for namidx, entry in enumerate(name_list): 
                    named_residue_dir[entry] = namidx+sse_adj[0]+gain_domain.start
            else: # If there is an unadressed SSE with length 3 or more, then add this to unindexed.
                if sse[1]-sse[0] > 3:
                    if debug: print(f"[DEBUG] GainDomain.create_indexing : No anchor found! \n {gain_domain.alignment_indices[sse[0]] = } \ns{gain_domain.alignment_indices[sse_end] = }")
                    unindexed.append(gain_domain.alignment_indices[sse[0]])
    # Patch the GPS into the nom_list
    labels = ["GPS-2","GPS-1","GPS+1"]
    for i, residue in enumerate(gain_domain.GPS.residue_numbers[:3]):
        #print(residue)
        nom_list[residue] = labels[i]
        indexing_dir["GPS"] = gain_domain.GPS.residue_numbers
        # Also cast this to the general indexing dictionary
        named_residue_dir[labels[i]] = gain_domain.GPS.residue_numbers[i]
    # FUTURE CHANGE : GPS assignment maybe needs to be more fuzzy -> play with the interval of the SSE 
    #       and not the explicit anchor. When anchor col is missing, the whole SSE wont be adressed
    # print([DEBUG] : GainDomain.create_indexing : ", nom_list)

    # Create a indexing File if specified
    if outdir is not None:
        indexing2longfile(gain_domain, nom_list, f"{outdir}/{gain_domain.name}.txt", offset=offset)

    return indexing_dir, indexing_centers, named_residue_dir, unindexed