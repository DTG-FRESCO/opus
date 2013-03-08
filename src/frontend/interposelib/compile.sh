g++ -DDEBUG -g -shared -fPIC -o liboverride.so log.cc proc_utils.cc uds_client.cc uds_message.pb.cc mywrite.cc -std=gnu++0x -I/home/nb466/protocolBuffers/include -L/home/nb466/protocolBuffers/lib -ldl -lrt -lprotobuf
g++ -DDEBUG log.cc uds_message.pb.cc server.cc -std=gnu++0x -I/home/nb466/protocolBuffers/include -L/home/nb466/protocolBuffers/lib -lprotobuf
#protoc uds_message.proto --cc_out=.
