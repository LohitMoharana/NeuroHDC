# Makefile for Cocotb execution
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# Paths to the Verilog files
PWD=$(shell pwd)
RTL_DIR=$(PWD)/../rtl

VERILOG_SOURCES += $(RTL_DIR)/delta_tokenizer.v
VERILOG_SOURCES += $(RTL_DIR)/hdc_bind_bundle.v
VERILOG_SOURCES += $(RTL_DIR)/top_shde_core.v

# Top module name
TOPLEVEL = top_shde_core
# Python test script name (without .py)
MODULE = test_shde_core

# Include Cocotb makefiles
include $(shell cocotb-config --makefiles)/Makefile.sim