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
        sse_sequence : dict
            DICT containing a sequence of all letters assigned to the residues with the key being the present residue
    '''
    sse_dict = {}

    with open(file) as f:

        for l in f.readlines():

            if l.startswith("ASG"):     # ASG is the per-residue ASSIGNMENT of SSE
                                        # LOC is already grouped from [start - ]
                items = l.split(None)   # [24] has the SSE one-letter code
                # Example lines:
                # items[i]:
                #  0    1 2    3    4    5             6         7         8         9        10
                #ASG  THR A  458  453    E        Strand   -123.69    131.11       4.2      ~~~~
                #ASG  SER A  459  454    E        Strand    -66.77    156.86      10.4      ~~~~
                # 3 is the PDB index, 4 is the enumerating index, this is crucial for avoiding offsets, always take 3
                sse_dict[int(items[3])] = items[5]

    return sse_dict

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
        print("No GPS residue present in this Domain. Is this really a GAIN?")
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

def find_boundaries(sse_dict, seq_len, bracket_size=50, domain_threshold=50, coil_weight=0):
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
    try:
        len(boundaries)
    except TypeError:
        print('No boundaries detected.')
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
    if maxk != None:
        gain_start, initial_boundary = boundaries[maxk], boundaries[maxk+1]
    
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

    # If you did not find the maxk previously:
    return None, None

def sse_seqence2bools(sse_list):
    '''
    Create a dictionary containing the actually detected alpha helices and beta sheets for all residues in sse_list, 
    using lower_case mode detection and the spacing variable
    '''
    sse_dict = {}
    sse_dict["AlphaHelix"] = []
    sse_dict["Strand"] = []

    hel_signal = np.zeros([len(sse_list)], dtype=int)
    she_signal = np.zeros([len(sse_list)], dtype=int)

    for i, res in enumerate(sse_list):
        if res == "H" or res == "G":
            hel_signal[i] = 1
        elif res == "E":
            she_signal[i] = 1

    return hel_signal, she_signal

def count_domain_sses(domain_start, domain_end, tuple_list=None, spacing=1, minimum_length=3, gain_start=0, sse_bool=None):
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

def get_subdomain_sse(sse_dict, subdomain_boundary, start, end, sse_sequence, stride_outlier_mode=False):
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
    #print(f"[DEBUG] sse_func.get_subdomain_sse : \n\t {helices = } \n\t {sheets = } \n\t {subdomain_boundary = }")

    # Parse boundaries, relevant for other uses of this function like enumerating other sections
    if subdomain_boundary == None:
        helix_upperbound = end
        sheet_lowerbound = start
    else:
        helix_upperbound = subdomain_boundary
        sheet_lowerbound = subdomain_boundary

    if stride_outlier_mode == False:    
        alpha, alpha_breaks = count_domain_sses(start,helix_upperbound, helices, spacing=1, minimum_length=3, gain_start=start) # PARSING BY SSE DICTIONARY
        beta, beta_breaks = count_domain_sses(sheet_lowerbound, end, sheets, spacing=1, minimum_length=2, gain_start=start) # 
    
    if stride_outlier_mode == True:
        hel_bool, she_bool = sse_seqence2bools(sse_sequence)
        alpha, alpha_breaks = count_domain_sses(start,helix_upperbound, helices, spacing=1, minimum_length=3, gain_start=start, sse_bool=hel_bool) # PARSING BY SSE-SEQUENCE
        beta, beta_breaks = count_domain_sses(sheet_lowerbound, end, sheets, spacing=1, minimum_length=2, gain_start=start, sse_bool=she_bool) # 
    #print(f"[DEBUG] sse_func.get_subdomain_sse : \n\t {alpha = } \n\t {beta = }")
    return alpha, beta, alpha_breaks, beta_breaks

#### NAMING SCHEME ####

def name_sse(sse_dict, subdomain_boundary, start, end, sse_sequence):
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
    alpha, beta, _, _ = get_subdomain_sse(sse_dict, subdomain_boundary, start, end, sse_sequence)

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