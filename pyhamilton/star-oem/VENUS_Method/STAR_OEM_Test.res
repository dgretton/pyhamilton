#pragma once
global resource Res_mlstar(1, 0xff0000, Translate("mlstar"));
global resource Res_HxFan(1, 0xff0000, Translate("HxFan"));
global resource Res_ML_STARlet(1, 0xff0000, Translate("ML_STARlet"));


function Res_mlstar_map(variable unit) variable { return(unit); }
function Res_mlstar_rmap(variable address) variable { return(address); }

function Res_HxFan_map(variable unit) variable { return(unit); }
function Res_HxFan_rmap(variable address) variable { return(address); }

function Res_ML_STARlet_map(variable unit) variable { return(unit); }
function Res_ML_STARlet_rmap(variable address) variable { return(address); }


namespace ResourceUnit {
     variable Res_mlstar;
     variable Res_HxFan;
     variable Res_ML_STARlet;
}
// $$author=Hamilton$$valid=0$$time=2024-09-06 14:25$$checksum=79960328$$length=085$$