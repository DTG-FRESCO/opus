g++ -g -shared -fPIC -o liboverride.so mywrite.C -std=gnu++0x -ldl
#g++ -shared -fPIC -o liboverride.so mywrite.C -L $HOME/protocolBuffers/lib -lprotobuf -ldl
#g++ -shared -o liboverride.so -L $HOME/protocolBuffers/lib -static -lprotobuf mywrite.C -ldl
