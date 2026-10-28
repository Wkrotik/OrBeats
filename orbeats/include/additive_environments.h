// Stock single-player environment scene IDs from the owned CUSA12878/2.04 catalog.
#pragma once
#include <stddef.h>
#include <string.h>
namespace BsdAdditive {
inline bool reviewed_environment(const char* name) {
    static const char* const names[]={"BTSEnvironment","BigMirrorEnvironment","BillieEnvironment","BritneyEnvironment","ColliderEnvironment","CrabRaveEnvironment","DaftPunkEnvironment","DefaultEnvironment","Dragons2Environment","DragonsEnvironment","EDMEnvironment","FitBeatEnvironment","GagaEnvironment","GreenDayEnvironment","GreenDayGrenadeEnvironment","HalloweenEnvironment","HipHopEnvironment","InterscopeEnvironment","KDAEnvironment","KaleidoscopeEnvironment","LatticeEnvironment","LinkinPark2Environment","LinkinParkEnvironment","LizzoEnvironment","MetallicaEnvironment","Monstercat2Environment","MonstercatEnvironment","NiceEnvironment","OriginsEnvironment","Panic2Environment","PanicEnvironment","PyroEnvironment","QueenEnvironment","RockMixtapeEnvironment","RocketEnvironment","SkrillexEnvironment","TheRollingStonesEnvironment","TheSecondEnvironment","TheWeekndEnvironment","TimbalandEnvironment","TriangleEnvironment","WeaveEnvironment"};
    if(!name)return false;
    for(size_t i=0;i<sizeof(names)/sizeof(names[0]);++i)if(!strcmp(name,names[i]))return true;
    return false;
}
}
