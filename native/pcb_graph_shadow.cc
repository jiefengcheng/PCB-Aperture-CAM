// PCB-owned process adapter over unmodified gfs_l0 DB0; no shared ABI changes.
#include "l0/interface0.h"
#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <limits>
int main(int argc,char**argv){
 if(argc<4){std::cerr<<"usage: build db csv tag | query db tag direction limit vid...\n";return 2;}
 l0::DB0Params p;p.db_dir=argv[2];unsigned long tag=std::stoul(argv[argc>4&&std::string(argv[1])=="build"?4:3]);
 if(tag>=255){std::cerr<<"invalid local tag\n";return 2;}p.tag=static_cast<l0::edge_tag_t>(tag);
 l0::DB0Ptr db;l0::Status s;
 if(std::string(argv[1])=="build")s=l0::DB0::BuildFromCSV(p,argv[3],&db);else s=l0::DB0::Open(p,&db);
 if(!s.ok()){std::cerr<<s.ToString()<<"\n";return 3;}
 if(std::string(argv[1])=="build"){std::cout<<"BUILT "<<db->GetNumEdges()<<"\n";return 0;}
 if(argc<7){std::cerr<<"missing query arguments\n";return 2;}
 std::string direction=argv[4];size_t limit=std::stoull(argv[5]);
 if(direction!="out"&&direction!="in"){std::cerr<<"unknown direction\n";return 2;}
 for(int i=6;i<argc;i++){
  auto raw=std::stoull(argv[i]);if(raw>=std::numeric_limits<l0::vid_t>::max()){std::cerr<<"VID overflow\n";return 2;}
  auto vid=static_cast<l0::vid_t>(raw);size_t count=0;bool stopped=false;
  auto visitor=[&](const l0::StorageEdgeRef&e){if(count>=limit){stopped=true;return false;}std::cout<<i-6<<" "<<e.a_vid()<<" "<<e.b_vid()<<" "<<unsigned(e.tag())<<"\n";++count;return true;};
  s=direction=="out"?db->ForEachEdgeByAFromShard(vid,visitor,p.tag):db->ForEachEdgeByB(vid,visitor,p.tag);
  if(!s.ok()){std::cerr<<s.ToString()<<"\n";return 3;}
  std::cout<<"END "<<i-6<<" "<<(stopped?"TRUNCATED":"COMPLETE")<<"\n";
 }
 return 0;
}
