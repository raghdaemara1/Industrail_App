import networkx as nx
import re
from typing import Optional
from neo4j import GraphDatabase
import os
from config import GRAPH_BACKEND, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

COMPONENT_PATTERN = re.compile(
    r'\b(inverter|motor|servo|sensor|encoder|valve|pump|'
    r'bearing|seal|gear|belt|conveyor|drive|plc|hmi|camera)\b',
    re.IGNORECASE
)

class Neo4jGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
        
    def build(self, alarm_records: list):
        if not alarm_records: return
        with self.driver.session() as session:
            for r in alarm_records:
                is_dict = isinstance(r, dict)
                aid = r.get("alarm_id") if is_dict else r.alarm_id
                machine = r.get("machine", "unknown") if is_dict else (r.machine or "unknown")
                desc = r.get("description", "") if is_dict else r.description
                cause = r.get("cause", "") if is_dict else r.cause
                r2 = r.get("reason_level_2", "") if is_dict else r.reason_level_2
                
                # Merge Alarm and Machine
                session.run(
                    "MERGE (a:Alarm {id: $aid}) "
                    "SET a.description = $desc, a.reason_2 = $r2 "
                    "MERGE (m:Machine {name: $machine}) "
                    "MERGE (a)-[:BELONGS_TO]->(m)",
                    aid=aid, desc=desc, r2=r2, machine=machine
                )
                
                for component in COMPONENT_PATTERN.findall(cause or ""):
                    c = component.lower()
                    session.run(
                        "MERGE (a:Alarm {id: $aid}) "
                        "MERGE (c:Component {name: $comp}) "
                        "MERGE (a)-[:CAUSES]->(c)",
                        aid=aid, comp=c
                    )

    def alarms_for_machine(self, machine: str) -> list:
        with self.driver.session() as session:
            res = session.run("MATCH (a:Alarm)-[:BELONGS_TO]->(m:Machine {name: $m}) RETURN a.id", m=machine)
            return [record["a.id"] for record in res]

    def alarms_for_component(self, component: str) -> list:
        with self.driver.session() as session:
            res = session.run("MATCH (a:Alarm)-[:CAUSES]->(c:Component {name: $c}) RETURN a.id", c=component)
            return [record["a.id"] for record in res]

    def shared_components(self, alarm_a: str, alarm_b: str) -> list:
        with self.driver.session() as session:
            res = session.run(
                "MATCH (a1:Alarm {id: $a1})-[:CAUSES]->(c:Component)<-[:CAUSES]-(a2:Alarm {id: $a2}) RETURN c.name",
                a1=alarm_a, a2=alarm_b
            )
            return [record["c.name"] for record in res]

    def component_risk_ranking(self) -> list:
        with self.driver.session() as session:
            res = session.run(
                "MATCH (a:Alarm)-[:CAUSES]->(c:Component) "
                "RETURN c.name as component, count(a) as count ORDER BY count DESC"
            )
            return [(record["component"], record["count"]) for record in res]

class AlarmGraph:
    """
    In-memory directed graph or Neo4j based on config.
    """
    def __init__(self):
        self.backend = GRAPH_BACKEND
        self.G = None
        self.neo = None
        
        if self.backend == "neo4j":
            try:
                self.neo = Neo4jGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
                # Test connection
                self.neo.driver.verify_connectivity()
            except Exception as e:
                print(f"Neo4j connection failed: {e}. Falling back to networkx memory graph.")
                self.backend = "networkx"
                self.neo = None
                
        if self.backend == "networkx":
            self.G = nx.DiGraph()

    def build(self, alarm_records: list):
        if self.backend == "neo4j" and self.neo:
            self.neo.build(alarm_records)
            return

        for r in alarm_records:
            is_dict = isinstance(r, dict)
            aid     = r.get("alarm_id") if is_dict else r.alarm_id
            machine = r.get("machine", "unknown") if is_dict else (r.machine or "unknown")
            desc = r.get("description", "") if is_dict else r.description
            cause = r.get("cause", "") if is_dict else r.cause
            r2 = r.get("reason_level_2", "") if is_dict else r.reason_level_2

            self.G.add_node(aid,     type="alarm",
                            description=desc,
                            reason_2=r2)
            self.G.add_node(machine, type="machine")
            self.G.add_edge(aid, machine, relation="BELONGS_TO")

            for component in COMPONENT_PATTERN.findall(cause or ""):
                c = component.lower()
                self.G.add_node(c, type="component")
                self.G.add_edge(aid, c, relation="CAUSES")

    def alarms_for_machine(self, machine: str) -> list:
        if self.backend == "neo4j" and self.neo: return self.neo.alarms_for_machine(machine)
        return [n for n in self.G.predecessors(machine) if self.G.nodes[n].get("type") == "alarm"]

    def alarms_for_component(self, component: str) -> list:
        if self.backend == "neo4j" and self.neo: return self.neo.alarms_for_component(component)
        if component not in self.G: return []
        return [n for n in self.G.predecessors(component) if self.G.nodes[n].get("type") == "alarm"]

    def shared_components(self, alarm_a: str, alarm_b: str) -> list:
        if self.backend == "neo4j" and self.neo: return self.neo.shared_components(alarm_a, alarm_b)
        if alarm_a not in self.G or alarm_b not in self.G: return []
        return list(set(self.G.successors(alarm_a)) & set(self.G.successors(alarm_b)))

    def component_risk_ranking(self) -> list:
        if self.backend == "neo4j" and self.neo: return self.neo.component_risk_ranking()
        comps = [
            (node, self.G.in_degree(node))
            for node, data in self.G.nodes(data=True)
            if data.get("type") == "component"
        ]
        return sorted(comps, key=lambda x: x[1], reverse=True)
