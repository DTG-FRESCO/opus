#! /bin/bash
set -e
set -x

export REPO_BASE=$PWD
mkdir -p dist/opus-$VERSION
cd dist/opus-$VERSION
export INSTALL_BASE=$PWD
mkdir -p python-libs
mkdir -p lib-base
export PATH=$INSTALL_BASE/lib-base/bin:$PATH

function setup_python(){
cd $INSTALL_BASE
PYTHONUSERBASE=$INSTALL_BASE/python-libs pip install --user --upgrade pytz setuptools google-apputils
}

function install_protobuf(){
cd $INSTALL_BASE
wget https://github.com/google/protobuf/releases/download/v2.6.1/protobuf-2.6.1.tar.gz
tar -xvzf protobuf-2.6.1.tar.gz
rm protobuf-2.6.1.tar.gz
cd protobuf-2.6.1
./configure --with-pic --disable-shared --prefix=$INSTALL_BASE/lib-base
make
make install
cd python
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=cpp
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION_VERSION=2
python setup.py build --cpp_implementation
PYTHONUSERBASE=$INSTALL_BASE/python-libs python setup.py install --user --cpp_implementation
}

function cleanup_protobuf(){
cd $INSTALL_BASE
rm -r protobuf-2.6.1
}

function install_jpype(){
cd $INSTALL_BASE
wget http://downloads.sourceforge.net/project/jpype/JPype/0.5.4/JPype-0.5.4.2.zip
unzip JPype-0.5.4.2.zip
rm JPype-0.5.4.2.zip
cd JPype-0.5.4.2
PYTHONUSERBASE=$INSTALL_BASE/python-libs python setup.py build
PYTHONUSERBASE=$INSTALL_BASE/python-libs python setup.py install --user
}

function cleanup_jpype(){
cd $INSTALL_BASE
rm -r JPype-0.5.4.2
}

function install_libcrypto(){
cd $INSTALL_BASE
wget https://www.openssl.org/source/openssl-1.0.2d.tar.gz
tar -xvzf openssl-1.0.2d.tar.gz
rm openssl-1.0.2d.tar.gz
cd openssl-1.0.2d
./config -fPIC -no-shared --prefix=$INSTALL_BASE/lib-base
make
make install
}

function cleanup_libcrypto(){
cd $INSTALL_BASE
rm -r openssl-1.0.2d
}

function install_pthread(){
cd $INSTALL_BASE
git clone git://sourceware.org/git/glibc.git
cd glibc
git checkout --track -b local_glibc-2.22 origin/release/2.22/master
mkdir build
cd build
../configure --prefix=$INSTALL_BASE/lib-base -fPIC
}

function cleanup_pthread(){
cd $INSTALL_BASE
rm -r glibc
}

function install_opus(){
cd $INSTALL_BASE

export PROJ_INCLUDE=$REPO_BASE/include
export PROTO_LIB_PATH=$INSTALL_BASE/lib-base/lib
export PROTO_INC_PATH=$INSTALL_BASE/lib-base/include
cd $REPO_BASE
make
mv lib/libopusinterpose.so $INSTALL_BASE
cd src/backend/
PYTHONUSERBASE=$INSTALL_BASE/python-libs pip install --upgrade --user .
}

function install_wrapper(){
cd $INSTALL_BASE

mkdir bin
cp $REPO_BASE/dist-bin/* .
cd bin
ln -s ../wrapper opusctl
ln -s ../wrapper last_cmd
ln -s ../wrapper gen_tree
ln -s ../wrapper gen_epsrc
ln -s ../wrapper gen_script
ln -s ../wrapper env_diff
}

function cleanup_libs(){
cd $INSTALL_BASE
rm -r lib-base
}

function zip_package(){
cd $INSTALL_BASE
cd ..
tar -vczf opus-$VERSION.tar.gz opus-$VERSION
}

setup_python
install_protobuf
install_jpype
install_libcrypto
#install_libpthread
install_opus
cleanup_protobuf
cleanup_jpype
cleanup_libcrypto
#cleanup_libpthread
cleanup_libs
install_wrapper
zip_package
