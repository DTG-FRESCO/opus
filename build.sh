#! /bin/bash
set -e
set -x

source build.vars.sh

export REPO_BASE=$PWD

export VERSION=$(git describe)

if [ $? -ne 0 ]; then
	echo "Attempting to build a non-tagged commit."
	exit 1
fi

export VERSION=${VERSION#v}

mkdir -p dist/opus-$VERSION
cd dist/opus-$VERSION
export INSTALL_BASE=$PWD
mkdir -p python-libs
mkdir -p lib
mkdir -p lib-base
echo $VERSION > VERSION
export PATH=$INSTALL_BASE/lib-base/bin:$PATH
export PYTHONUSERBASE=$INSTALL_BASE/python-libs

function setup_python(){
cd $INSTALL_BASE
pip install --user --upgrade pytz setuptools google-apputils
}

function build_deps(){
cd $INSTALL_BASE
pip install --user --upgrade jinja2
}

function install_protobuf(){
cd $INSTALL_BASE
wget $PROTOBUF_URL
tar -xvzf $PROTOBUF_ARCH
rm $PROTOBUF_ARCH
cd $PROTOBUF_DIR
./configure --with-pic --disable-shared --prefix=$INSTALL_BASE/lib-base
make
make install
cd python
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=cpp
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION_VERSION=2
python setup.py build --cpp_implementation
python setup.py install --user --cpp_implementation --single-version-externally-managed --root=/
}

function cleanup_protobuf(){
cd $INSTALL_BASE
rm -r $PROTOBUF_DIR
}

function install_jpype(){
cd $INSTALL_BASE
wget $JPYPE_URL
unzip $JPYPE_ARCH
rm $JPYPE_ARCH
cd $JPYPE_DIR
python setup.py build
python setup.py install --user
}

function cleanup_jpype(){
cd $INSTALL_BASE
rm -r $JPYPE_DIR
}

function install_libcrypto(){
cd $INSTALL_BASE
git clone $OPENSSL_REPO
cd $OPENSSL_DIR
git checkout $OPENSSL_TAG
./config -fPIC -no-shared --prefix=$INSTALL_BASE/lib-base
make
make install
}

function cleanup_libcrypto(){
cd $INSTALL_BASE
rm -rf $OPENSSL_DIR
}

function install_opus(){
cd $INSTALL_BASE

export PROJ_INCLUDE=$REPO_BASE/include
export LIBRARY_PATH=$INSTALL_BASE/lib-base/lib:$LIBRARY_PATH
export CPATH=$INSTALL_BASE/lib-base/include:$CPATH
cd $REPO_BASE
make
mv lib/libopusinterpose.so $INSTALL_BASE/lib
cd src/backend/
pip install --upgrade --user .
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
build_deps
install_opus
cleanup_protobuf
cleanup_jpype
cleanup_libcrypto
cleanup_libs
install_wrapper
zip_package
