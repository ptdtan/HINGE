#!/usr/bin/env python

import sys
import os
import subprocess
from parse_read import *
import numpy as np
import networkx as nx
import itertools
from pbcore.io import FastaIO

filedir = sys.argv[1]
filename = sys.argv[2]
graphml_path = sys.argv[3]

in_graph = nx.read_graphml(graphml_path)

reads = sorted(list(set([int(x.split("_")[0].lstrip("B")) for x in in_graph.nodes()])))

dbshow_reads = ' '.join([str(x+1) for x in reads])

# DBshow_cmd = "DBshow "+ filedir+'/'+ filename+' '+dbshow_reads
# stream = subprocess.Popen(DBshow_cmd.split(),
#                                   stdout=subprocess.PIPE,bufsize=1)
# reads_queried = parse_read(stream.stdout)
# read_dict = {}
# for read_id,read in itertools.izip(reads,reads_queried):
#     rdlen = len(read[1])
# #     print read
#     read_dict[read_id] = read

complement = {'A':'T','C': 'G','T':'A', 'G':'C','a':'t','t':'a','c':'g','g':'c'}


def rev_node(node):
    node_id = node.split('_')[0]
    return node_id + '_' + str(1-int(node.split('_')[1]))



def reverse_complement(string):
    return "".join(map(lambda x:complement[x],reversed(string)))

def get_string(path):
    # print path
    ret_str = ''
    for itm in path:
        # print itm
        read_id,rd_orientation = itm[0].split("_")
        if rd_orientation == '1':
            assert itm[1][0] >= itm[1][1]
            str_st = itm[1][1]
            str_end = itm[1][0]
            read_str = "ACGT" #read_dict[int(read_id.lstrip("B"))][1][str_st:str_end]
        else:

            assert itm[1][0] <= itm[1][1]
            str_st = itm[1][0]
            str_end = itm[1][1]
            read_str = "ACGT" # reverse_complement(read_dict[int(read_id.lstrip("B"))][1][str_st:str_end])
#         print str_st,str_end
#         print read_id
#         print read_dict[int(read_id)][str_st:str_end]
#         print read_str
        # print 'read len',len(read_str)
        ret_str += read_str
    # print len(path), len(ret_str)
    return ret_str



# the following loop removes start/end inconsistencies created in pruning and clipping
for vert in in_graph:

    vert_id, vert_or = vert.split("_")
    if vert_or == '1':
        continue

    read_starts = [(in_graph.edge[x][vert]['read_b_start']) for x in in_graph.predecessors(vert)]
    read_starts.append(0)
    read_ends = [(in_graph.edge[vert][x]['read_a_start']) for x in in_graph.successors(vert)]    
    read_ends.append(100000)

    if max(read_starts) > min(read_ends):

        for pred in in_graph.predecessors(vert):
            in_graph.remove_edge(pred,vert)
            in_graph.remove_edge(rev_node(vert),rev_node(pred))



print "here0"

vertices_of_interest = set([x for x in in_graph if in_graph.in_degree(x) != 1 or in_graph.out_degree(x) != 1])

read_tuples = {}

for vert in vertices_of_interest:

    vert_id, vert_or = vert.split("_")
    if vert_or == '1':
        continue
    vert_len = 50000 # len(read_dict[int(vert_id)][1])
#     print vert_len
    read_starts = [(in_graph.edge[x][vert]['read_b_start']) for x in in_graph.predecessors(vert)]
    read_ends = [(in_graph.edge[vert][x]['read_a_start']) for x in in_graph.successors(vert)]
    if read_starts:
        read_start = max(read_starts)
    else:
        read_start = 0
    if read_ends:
        read_end = min(read_ends)
    else:
        read_end = vert_len
    read_tuples[vert] = (read_start,read_end)
    # print read_starts, read_ends, vert


for vert in vertices_of_interest:

    vert_id, vert_or = vert.split("_")
    if vert_or == '1':
        read_tuples[vert] = read_tuples[vert_id+"_0"]


start_vertices = [x for x in vertices_of_interest if in_graph.in_degree(x) == 0 or in_graph.out_degree(x) > 1]
h = nx.DiGraph()

read_tuples_raw = {}
for vertex in vertices_of_interest:
    successors = in_graph.successors(vertex)
    if successors:
        succ = successors[0]
        d =  in_graph.get_edge_data(vertex,succ)
        read_tuples_raw[vertex] = (d['read_a_start_raw'], d['read_a_end_raw'])
    else:
        predecessors = in_graph.predecessors(vertex)
        if not len(predecessors) == 0:
            pred = predecessors[0]
            d =  in_graph.get_edge_data(pred,vertex)
            read_tuples_raw[vertex] = (d['read_b_start_raw'], d['read_b_end_raw'])
        else:
            read_tuples_raw[vertex] = (0,0)


print "here1"

for vertex in vertices_of_interest:
    h.add_node(vertex)
    if vertex.split("_")[1] == '0':
        path_var = [(vertex,(read_tuples[vertex][0], read_tuples[vertex][1]))]
    else:
        path_var = [(vertex,(read_tuples[vertex][1], read_tuples[vertex][0]))]
    #print path_var
    segment = get_string(path_var)
    h.node[vertex]['start_read'] = path_var[0][1][0]
    h.node[vertex]['end_read'] = path_var[0][1][1]
    h.node[vertex]['path'] = [vertex]
    h.node[vertex]['segment'] = segment

vertices_used = set([x for x in h.nodes()])
contig_no = 1
for start_vertex in vertices_of_interest:
    first_out_vertices = in_graph.successors(start_vertex)
    # print start_vertex, first_out_vertices
    for vertex in first_out_vertices:
        predecessor = start_vertex
        start_vertex_id,start_vertex_or = start_vertex.split("_")
        cur_vertex = vertex
        if start_vertex_or == '0':
            cur_path = [(start_vertex,(read_tuples[start_vertex][1],
                                       in_graph.edge[start_vertex][cur_vertex]['read_a_start']))]
        elif start_vertex_or == '1':
            cur_path = [(start_vertex,(read_tuples[start_vertex][0],
                                       in_graph.edge[start_vertex][cur_vertex]['read_a_start']))]

        while cur_vertex not in vertices_of_interest:
            successor = in_graph.successors(cur_vertex)[0]
            start_point = in_graph.edge[predecessor][cur_vertex]['read_b_start']
            end_point = in_graph.edge[cur_vertex][successor]['read_a_start']
            cur_path.append((cur_vertex,(start_point,end_point)))
            vertices_used.add(cur_vertex)
            predecessor = cur_vertex
            cur_vertex = successor

        stop_vertex_id, stop_vertex_or = cur_vertex.split("_")
        if stop_vertex_or == '0':
            cur_path.append((cur_vertex,(in_graph.edge[predecessor][cur_vertex]['read_b_start'],
                        read_tuples[cur_vertex][0])))
        elif stop_vertex_or == '1':
            cur_path.append((cur_vertex,(in_graph.edge[predecessor][cur_vertex]['read_b_start'],
                        read_tuples[cur_vertex][1])))


        node_name = str(contig_no)
        h.add_node(node_name)
        contig_no += 1
#         print cur_path
        node_path = [x[0] for x in cur_path]
        h.node[node_name]['path'] = node_path
        h.node[node_name]['start_read'] = cur_path[0][1][0]
        h.node[node_name]['end_read'] = cur_path[-1][1][1]
        h.node[node_name]['segment'] = get_string(cur_path)
        h.add_edges_from([(start_vertex,node_name),(node_name,cur_vertex)])
#         paths.append(cur_path)

#print read_tuples

print "here2"

while set(in_graph.nodes())-vertices_used:
    vert = list(set(in_graph.nodes())-vertices_used)[0]
    vert_id,vert_or = vert.split("_")
    if vert_or == '0':
        read_start = min( min([(in_graph.edge[x][vert]['read_b_start']) for x in in_graph.predecessors(vert)]),
                         max([(in_graph.edge[vert][x]['read_a_start']) for x in in_graph.successors(vert)]))
        read_end = max( min([(in_graph.edge[x][vert]['read_b_start']) for x in in_graph.predecessors(vert)]),
                         max([(in_graph.edge[vert][x]['read_a_start']) for x in in_graph.successors(vert)]))
        vertRC = vert_id+"_1"
    else:
        read_start = max( min([(in_graph.edge[x][vert]['read_b_start']) for x in in_graph.predecessors(vert)]),
                         max([(in_graph.edge[vert][x]['read_a_start']) for x in in_graph.successors(vert)]))
        read_end = min( min([(in_graph.edge[x][vert]['read_b_start']) for x in in_graph.predecessors(vert)]),
                         max([(in_graph.edge[vert][x]['read_a_start']) for x in in_graph.successors(vert)]))
        vertRC = vert_id+"_0"

    successor_start = in_graph.successors(vert)[0]
    d =  in_graph.get_edge_data(vert,successor_start)
    read_tuples_raw[vert] = (d['read_a_start_raw'], d['read_a_end_raw'])

    successor_start = in_graph.successors(vertRC)[0]
    d =  in_graph.get_edge_data(vertRC,successor_start)
    read_tuples_raw[vertRC] = (d['read_a_start_raw'], d['read_a_end_raw'])

    h.add_node(vert)
    node_path = [vert]
    h.node[vert]['path'] = node_path
    h.node[vert]['start_read'] = read_start
    h.node[vert]['end_read'] = read_end
    h.node[vert]['segment'] = get_string([(vert,(read_start, read_end))])
    vertices_used.add(vert)

    first_out_vertices = in_graph.successors(vert)
    for vertex in first_out_vertices:
        predecessor = vert
        cur_vertex = vertex
        cur_path = []
        while cur_vertex != vert:
            successor = in_graph.successors(cur_vertex)[0]
            start_point = in_graph.edge[predecessor][cur_vertex]['read_b_start']
            end_point = in_graph.edge[cur_vertex][successor]['read_a_start']
            cur_path.append((cur_vertex,(start_point,end_point)))
            vertices_used.add(cur_vertex)
            predecessor = cur_vertex
            cur_vertex = successor
        node_name = str(contig_no)
        h.add_node(node_name)
        contig_no += 1
#         print cur_path

        node_path = [x[0] for x in cur_path]
        h.node[node_name]['path'] = node_path
        try:
            h.node[node_name]['start_read'] = cur_path[0][1][0]
            h.node[node_name]['end_read'] = cur_path[-1][1][1]
        except:
            print path_var
            raise
        h.node[node_name]['segment'] = get_string(cur_path)
        h.add_edges_from([(vert,node_name),(node_name,vert)])

    if vertRC not in vertices_used:
        h.add_node(vertRC)
        h.node[vertRC]['segment'] = get_string([(vertRC,(read_end, read_start))])
        h.node[vertRC]['path'] = [vertRC]
        h.node[vertRC]['start_read'] = read_end
        h.node[vertRC]['end_read'] = read_start

        vertices_used.add(vertRC)
        first_out_vertices = in_graph.successors(vertRC)
        for vertex in first_out_vertices:
            predecessor = vertRC
            cur_vertex = vertex
            cur_path = []
            while cur_vertex != vertRC:
                successor = in_graph.successors(cur_vertex)[0]
                start_point = in_graph.edge[predecessor][cur_vertex]['read_b_start']
                end_point = in_graph.edge[cur_vertex][successor]['read_a_start']
                cur_path.append((cur_vertex,(start_point,end_point)))
                vertices_used.add(cur_vertex)
                predecessor = cur_vertex
                cur_vertex = successor
            node_name = str(contig_no)
            h.add_node(node_name)
            contig_no += 1
    #         print cur_path

            node_path = [x[0] for x in cur_path]
            h.node[node_name]['path'] = node_path
            h.node[node_name]['start_read'] = cur_path[0][1][0]
            h.node[node_name]['end_read'] = cur_path[-1][1][1]
            h.node[node_name]['segment'] = get_string(cur_path)
            # print len(cur_path)
            h.add_edges_from([(vertRC,node_name),(node_name,vertRC)])



outfile = filedir + '/' + filename + ".edges.list"
# outfile_norevcomp = filedir + '/' + filename + ".norevcomp.edges.list"


vert_to_merge = [x for x in h.nodes() if len(h.successors(x)) == 1 and len(h.predecessors(h.successors(x)[0])) == 1 and 
 x != h.successors(x)[0] and
 len(nx.node_connected_component(h.to_undirected(), x)) > 2]

print "here3"


vert_to_merge = [x for x in h.nodes() if len(h.successors(x)) == 1 and len(h.predecessors(h.successors(x)[0])) == 1 and
    x != h.successors(x)[0] ]

# while True:

countdown = len(vert_to_merge)

for vert in vert_to_merge:

    # and
    # len(nx.node_connected_component(h.to_undirected(), x)) > 2]

    print countdown
    countdown -= 1

    if len(h.successors(x)) != 1 or len(h.predecessors(h.successors(x)[0])) != 1 or x == h.successors(x)[0]:
        continue

    # print "vert_to_merge: "+str(len(vert_to_merge))

    # if not vert_to_merge:
    #     break

    # vert = vert_to_merge[0]
    #print vert,

    succ = h.successors(vert)[0]
    preds = h.predecessors(vert)

    if succ in preds:
        continue

    h.node[succ]['segment'] =  h.node[vert]['segment'] + h.node[succ]['segment']
    h.node[succ]['path'] = h.node[vert]['path'] + h.node[succ]['path'][1:]

    for pred in preds:
        #print pred, succ
        h.add_edges_from([(pred,succ)])
        h.remove_edge(pred,vert)

    h.remove_edge(vert,succ)
    h.remove_node(vert)


path_to_vert = {}
RCmap = {}

for i, vert in enumerate(h.nodes()):
    path =  h.node[vert]['path']
    path_to_vert[':'.join(path)] = vert 

for path in path_to_vert:
    path_to_search = ':'.join(list(reversed([ x.split('_')[0]+'_'+str(1-int(x.split('_')[1])) for x in path.split(':')])))
    RCmap[path_to_vert[path]] = path_to_vert[path_to_search]

# print path_to_vert        


# print RCmap
# print [x for x in h.edges()]

print "here4"


vert_to_merge = [x for x in h.nodes() if len(h.successors(x)) == 1 and len(h.predecessors(h.successors(x)[0])) == 1 and
    x != h.successors(x)[0] and h.successors(h.successors(x)[0])[0]== x and len(h.successors(h.successors(x)[0])) == 1 
    and len(nx.node_connected_component(h.to_undirected(), x)) == 2]


for vert in vert_to_merge:

    # if not vert_to_merge:
    #     break

    # vert = vert_to_merge[0]

    if vert not in h.nodes():
        continue

    if len(h.successors(vert)) == 1 and h.successors(vert)[0] == vert:
        continue

    succ = h.successors(vert)[0]

    # print vert, succ

    vertRC = RCmap[vert]
    # print vert, vertRC

    predRC = h.predecessors(vertRC)[0]

    # print h.node[vert]['path']
    # print h.node[succ]['path']

    h.node[succ]['segment'] =  h.node[vert]['segment'] + h.node[succ]['segment']
    h.node[predRC]['segment'] =  h.node[predRC]['segment'] + h.node[vertRC]['segment']

    h.node[succ]['path'] = h.node[vert]['path'] + h.node[succ]['path']
    h.node[predRC]['path'] = h.node[predRC]['path'] + h.node[vertRC]['path']

    # print vert, succ, predRC, vertRC

    h.add_edges_from([(succ,succ)])
    h.add_edges_from([(predRC,predRC)])

    h.remove_node(vert)
    h.remove_node(vertRC)





for  i, vert in enumerate(h.nodes()):
    print i,len(h.node[vert]['path'])

cnt = 0
with open(outfile, 'w') as f:
    for i,node in enumerate(h.nodes()):
        #print node
        #print h.node[node]
        path = h.node[node]['path']
        h.node[node]['contig_id'] = cnt
        cnt += 1
        f.write('>Unitig%d\n'%(i))
        if len(path) == 1:
            #print path[0]
            f.write(' '.join([path[0].split('_')[0], path[0].split('_')[1], str(read_tuples_raw[path[0]][0]), str(read_tuples_raw[path[0]][1])]) + '\n')
        for j in range(len(path)-1):
            nodeA = path[j].lstrip("B")
            nodeB = path[j+1].lstrip("B")

            d =  in_graph.get_edge_data(path[j],path[j+1])
            try:
                f.write('%s %s %s %s %d %d %d %d %d\n'%(nodeA.split('_')[0],nodeA.split('_')[1]  , nodeB.split('_')[0],
                    nodeB.split('_')[1], -d['read_a_start_raw'] + d['read_a_end_raw'] - d['read_b_start_raw'] + d['read_b_end_raw'],
                    d['read_a_start_raw'], d['read_a_end_raw'], d['read_b_start_raw'], d['read_b_end_raw']))
            except:
                print "in error"
                print nodeB
                print node
                print  h.node[node]['start_read']
                print  h.node[node]['end_read']
                print  h.node[node]['path']
                print  len(h.node[node]['segment'])
                print d
                raise


# one_sided_contigs = []

observed_paths = []
cnt = 0

out_graphml_name = filedir + '/' + filename +'_draft.graphml'


gfaname = filedir + '/' + filename+ '_draft_python.gfa'
if len(sys.argv) > 3:
    consensus_name = sys.argv[3]
else:
    consensus_name = ''

consensus_contigs = []
try:
    with open(consensus_name) as f:
        for line in f:
            if line[0] != '>':
                consensus_contigs.append(line.strip())
except:
    pass
# for  i, vert in enumerate(h.nodes()):
#    print i,len(h.node[vert]['path']), len(h.node[vert]['segment']), len(consensus_contigs[i])


one_sided_contigs = []

observed_paths = []

for i, vert in enumerate(h.nodes()):
    path =  [x.split('_')[0] for x in h.node[vert]['path']]
    path_to_search = list(reversed(path))
    if path_to_search not in observed_paths:
        observed_paths.append(path)
        one_sided_contigs.append(h.node[vert]['segment'])



# commented out the block below so that the non-reverse-complemented contigs are not produced here

# out_nonrevcomp_name = filedir + '/' + filename +'_nonrevcomp.fasta'
# writer = FastaIO.FastaWriter(out_nonrevcomp_name)
# for i, ctg in enumerate(one_sided_contigs):
#     print i, len(ctg)
#     new_header = str(i)
#     writer.writeRecord(new_header, ctg)






#last =  h.nodes()[-1]
#print h.node[last]
#path_last = h.node[last]['path']



#for i in range(len(path_last)-1):
#    read_a = path_last[i]
#    read_b = path_last[i+1]
#    print read_a, read_b, in_graph.edge[read_a][read_b]

for i,node in enumerate(h.nodes()):
     h.node[node]['path'] = ';'.join(h.node[node]['path'])
nx.write_graphml(h,out_graphml_name)


# with open(gfaname,'w') as f:
#     f.write("H\tVN:Z:1.0\n")
#     for i,vert in enumerate(h.nodes()):
#         seg = h.node[vert]['segment']
#         print len(seg)

#         seg_line = "S\t"+vert+"\t"+seg + '\n'
#         f.write(seg_line)
#     for edge in h.edges():
#         edge_line = "L\t"+edge[0]+"\t+\t"+edge[1]+"\t+\t0M\n"
#         f.write(edge_line)


